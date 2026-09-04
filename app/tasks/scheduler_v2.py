"""
Scheduler v2 - Ejecuta escaneos continuamente de forma desacoplada
El frontend se puede reiniciar sin interrumpir los escaneos
"""

import asyncio
import logging
from typing import Dict
from datetime import datetime, timedelta
from app.core.config import settings
from app.services.scan_service_v2 import scan_service
from app.core.database import SessionLocal
from app.models.plant import Plant
from app.services.alarm_detector_v2 import alarm_detector

logger = logging.getLogger(__name__)

class SchedulerV2:
    """
    Planificador de tareas:
    - Ejecuta ciclos de escaneo cada N segundos
    - Verifica recordatorios de alarmas cada hora
    - Limpia datos antiguos
    - Desacoplado del frontend
    """
    
    def __init__(self):
        self.running = False
        self.paused = False  # Para permitir acciones manuales prioritarias
        self.task = None
        self.last_scan_time = None
        self.last_reminder_check = None
        self.scan_interval_seconds = settings.SCAN_INTERVAL_SECONDS or 300  # 5 minutos por defecto
    
    async def start(self):
        """Inicia el scheduler"""
        if self.running:
            logger.warning("Scheduler ya está corriendo")
            return
        
        self.running = True
        self.paused = False
        logger.info(f"Scheduler iniciado (intervalo: {self.scan_interval_seconds}s)")
        
        self.task = asyncio.create_task(self._run_loop())
    
    async def stop(self):
        """Para el scheduler"""
        self.running = False
        self.paused = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Scheduler detenido")
    
    async def pause_for_action(self):
        """
        Pausa el scheduler para permitir una acción manual (Escanear/Reporte).
        El scheduler se reanudará automáticamente cuando se detecte que scan_service ya no está escaneando.
        """
        self.paused = True
        logger.info("Scheduler PAUSADO para acción manual")
    
    async def resume(self):
        """Reanuda el scheduler después de una acción manual"""
        self.paused = False
        self.last_scan_time = datetime.utcnow()  # Resetear timer para evitar ciclo inmediato
        logger.info("Scheduler REANUDADO después de acción manual")
    
    async def _run_loop(self):
        """Bucle principal del scheduler"""
        # Esperar 30 segundos antes del primer escaneo para dar tiempo a cargar
        logger.info("Esperando 30s antes del primer escaneo...")
        await asyncio.sleep(30)
        
        while self.running:
            try:
                now = datetime.utcnow()
                
                # Si está pausado, solo esperar sin ejecutar nada
                if self.paused:
                    await asyncio.sleep(5)
                    continue
                
                # Comprobar si scan_service está ocupado (acción manual todavía corriendo)
                if scan_service.is_scanning():
                    await asyncio.sleep(5)
                    continue
                
                # Ejecutar ciclo de escaneo
                if self._should_run_scan(now):
                    logger.info("Iniciando ciclo de escaneo...")
                    try:
                        await scan_service.scan_all_plants()
                        self.last_scan_time = now
                    except Exception as e:
                        logger.error(f"Error en ciclo de escaneo: {e}")
                
                # Verificar recordatorios de alarmas cada hora
                if self._should_check_reminders(now):
                    logger.info("Verificando recordatorios de alarmas...")
                    try:
                        db = SessionLocal()
                        await alarm_detector.check_reminders(db)
                        db.close()
                        self.last_reminder_check = now
                    except Exception as e:
                        logger.error(f"Error verificando recordatorios: {e}")
                
                # Hacer limpieza de datos antiguos
                if self._should_cleanup(now):
                    logger.info("Ejecutando limpieza de datos...")
                    try:
                        await self._cleanup_old_data()
                    except Exception as e:
                        logger.error(f"Error en limpieza: {e}")
                
                # Esperar antes del próximo ciclo
                await asyncio.sleep(10)  # Verificar cada 10 segundos
            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error no esperado en scheduler loop: {e}")
                await asyncio.sleep(10)
    
    def get_status(self) -> Dict:
        """Retorna estado actual del scheduler"""
        return {
            "running": self.running,
            "paused": self.paused,
            "last_scan_time": self.last_scan_time.isoformat() if self.last_scan_time else None,
            "last_reminder_check": self.last_reminder_check.isoformat() if self.last_reminder_check else None,
            "scan_interval_seconds": self.scan_interval_seconds,
            "current_plant": scan_service.current_plant_name,
            "is_scanning": scan_service.is_scanning()
        }
    
    def _should_run_scan(self, now: datetime) -> bool:
        """Scanning only runs via manual "iniciar" (scan_service.start_manual_loop).
        El scheduler NO lanza escaneos automáticos; así no se abren decenas de
        openvpn en paralelo que agotan el adaptador TAP y no se conecta sin que
        el usuario lo pida."""
        return False
    
    def _should_check_reminders(self, now: datetime) -> bool:
        """Determina si debe verificarse recordatorios (cada hora)"""
        if self.last_reminder_check is None:
            return True
        
        time_since_last_check = (now - self.last_reminder_check).total_seconds()
        return time_since_last_check >= 3600  # 1 hora
    
    def _should_cleanup(self, now: datetime) -> bool:
        """Determina si debe ejecutarse limpieza (cada 6 horas)"""
        if not hasattr(self, 'last_cleanup_time'):
            self.last_cleanup_time = now
            return False
        
        time_since_last_cleanup = (now - self.last_cleanup_time).total_seconds()
        if time_since_last_cleanup >= 21600:  # 6 horas
            self.last_cleanup_time = now
            return True
        return False
    
    async def _cleanup_old_data(self):
        """
        Limpia datos antiguos:
        - Escaneos más viejos que 30 días
        - Alarmas resueltas más viejas que 90 días
        """
        from app.models.scan import Scan
        from app.models.alarm import Alarm
        
        db = SessionLocal()
        try:
            # Limpiar scans antiguos
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            old_scans = db.query(Scan).filter(Scan.created_at < thirty_days_ago).all()
            for scan in old_scans:
                db.delete(scan)
            logger.info(f"Eliminados {len(old_scans)} escaneos antiguos")
            
            # Limpiar alarmas resueltas antiguas
            ninety_days_ago = datetime.utcnow() - timedelta(days=90)
            old_alarms = db.query(Alarm).filter(
                Alarm.status == 'resolved',
                Alarm.resolved_at < ninety_days_ago
            ).all()
            for alarm in old_alarms:
                db.delete(alarm)
            logger.info(f"Eliminadas {len(old_alarms)} alarmas antiguas")
            
            db.commit()
        
        except Exception as e:
            logger.error(f"Error en limpieza de datos: {e}")
            db.rollback()
        
        finally:
            db.close()
    
# Instancia global
scheduler = SchedulerV2()

# Importaciones necesarias
from typing import Dict

async def start_scheduler():
    """Función para iniciar scheduler al arrancar la aplicación"""
    await scheduler.start()

async def stop_scheduler():
    """Función para parar scheduler al cerrar la aplicación"""
    await scheduler.stop()
