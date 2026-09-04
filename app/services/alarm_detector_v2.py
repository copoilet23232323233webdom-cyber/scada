"""
Sistema de Alarmas v2 - Estados profesionales y detección automática
Estados: Verde (OK), Amarillo (parcial), Rojo (crítico)
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Tuple
from sqlalchemy.orm import Session
from app.models.alarm import Alarm, AlarmType, AlarmStatus
from app.models.plant import Plant
from app.models.gateway import Gateway, GatewayStatus
from app.models.card import Card, CardStatus
from app.services.email_service import email_service
from app.core.config import settings
from app.core.database import SessionLocal

logger = logging.getLogger(__name__)

class AlarmDetector:
    """Detecta y genera alarmas automáticamente"""
    
    # Umbrales
    RESPONSE_TIME_YELLOW_MS = 3000   # discovery ~1.6s + scan ~0.5s = ~2.1s normal
    RESPONSE_TIME_RED_MS = 6000      # 3x normal para considerar latencia de red
    FAILED_CARDS_YELLOW_PERCENT = 25  # 25% tarjetas caídas = amarillo
    FAILED_CARDS_RED_PERCENT = 75     # 75% tarjetas caídas = rojo
    
    def __init__(self):
        self.db: Optional[Session] = None
    
    def analyze_card_status(self, card: Card) -> Tuple[str, Optional[str]]:
        """
        Analiza estado de una tarjeta
        Retorna (estado, alarma_type)
        Estados: green, yellow, red
        """
        if card.disabled or card.maintenance_mode:
            return (CardStatus.DISABLED, None)
        
        alarm_type = None
        
        # Verificar alarmas
        if card.communication_alarm or not card.communication_ok:
            alarm_type = AlarmType.COMMUNICATION
            return (CardStatus.RED, alarm_type)
        
        if card.sec_alarm:
            alarm_type = AlarmType.SEC
            return (CardStatus.YELLOW, alarm_type)
        
        if card.overvoltage_alarm:
            alarm_type = AlarmType.OVERVOLTAGE
            return (CardStatus.YELLOW, alarm_type)
        
        # Si comunica bien
        return (CardStatus.GREEN, None)
    
    def analyze_gateway_status(self, gateway: Gateway) -> Tuple[str, Optional[str], str]:
        """
        Analiza estado de un Gateway
        Retorna (estado, alarma_type, descripcion)
        Estados: green, yellow, red
        """
        if gateway.maintenance_mode:
            return (GatewayStatus.UNKNOWN, None, "Mantenimiento")
        
        # Si no hay tarjetas encontradas
        if gateway.total_cards == 0:
            return (GatewayStatus.RED, AlarmType.GATEWAY_DOWN, "No responde")
        
        # Calcular porcentaje de fallos
        if gateway.total_cards > 0:
            failed_percent = (gateway.failed_cards / gateway.total_cards) * 100
        else:
            failed_percent = 0
        
        # Análisis de estado
        status = GatewayStatus.GREEN
        alarm_type = None
        description = "OK"
        
        # Rojo: Gateway caído
        if gateway.total_cards == 0 or gateway.response_time_ms is None:
            status = GatewayStatus.RED
            alarm_type = AlarmType.GATEWAY_DOWN
            description = "No responde"
        
        # Rojo: Todas las tarjetas caídas
        elif gateway.failed_cards == gateway.total_cards:
            status = GatewayStatus.RED
            alarm_type = AlarmType.COMMUNICATION
            description = "Todas las tarjetas sin comunicación"
        
        # Rojo: Tiempo de respuesta muy alto
        elif gateway.response_time_ms and gateway.response_time_ms > self.RESPONSE_TIME_RED_MS:
            status = GatewayStatus.RED
            alarm_type = AlarmType.LOW_RESPONSE
            description = f"Respuesta lenta ({gateway.response_time_ms}ms)"
        
        # Amarillo: Muchas tarjetas caídas
        elif failed_percent > self.FAILED_CARDS_YELLOW_PERCENT:
            status = GatewayStatus.YELLOW
            alarm_type = AlarmType.COMMUNICATION
            description = f"{gateway.failed_cards}/{gateway.total_cards} tarjetas sin comunicación"
        
        # Amarillo: Tiempo de respuesta medio
        elif gateway.response_time_ms and gateway.response_time_ms > self.RESPONSE_TIME_YELLOW_MS:
            status = GatewayStatus.YELLOW
            alarm_type = AlarmType.LOW_RESPONSE
            description = f"Respuesta media ({gateway.response_time_ms}ms)"
        
        # Amarillo: LoRa no OK
        elif not gateway.lora_ok:
            status = GatewayStatus.YELLOW
            description = "LoRa no OK"
        
        return (status, alarm_type, description)
    
    def analyze_plant_status(self, plant: Plant) -> Tuple[str, str]:
        """
        Analiza estado general de una planta
        Retorna (estado, descripcion)
        """
        from app.core.database import SessionLocal
        db = SessionLocal()
        
        try:
            gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
            
            if not gateways:
                return ("red", "Sin gateways configurados")
            
            # Contar estados
            red_count = 0
            yellow_count = 0
            
            for gw in gateways:
                gw_status, _, _ = self.analyze_gateway_status(gw)
                if gw_status == GatewayStatus.RED:
                    red_count += 1
                elif gw_status == GatewayStatus.YELLOW:
                    yellow_count += 1
            
            # Decisión final
            if red_count > 0:
                return ("red", f"{red_count} gateways en rojo")
            elif yellow_count > 0:
                return ("yellow", f"{yellow_count} gateways en amarillo")
            else:
                return ("green", "Todo correcto")
        
        finally:
            db.close()
    
    async def check_and_create_alarms(self, db: Session, gateway: Gateway):
        """
        Verifica estado de Gateway y crea alarmas necesarias
        Si el gateway se recupera, resuelve automáticamente las alarmas activas
        No crea alarmas en modo DEMO o si no hay VPN real conectada
        """
        from app.services.vpn_service_v2 import vpn_service
        
        status, alarm_type, description = self.analyze_gateway_status(gateway)
        
        # Actualizar estado del gateway
        gateway.status = status
        gateway.updated_at = datetime.utcnow()
        db.commit()
        
        # Detectar si estamos en modo DEMO:
        # - demo_mode flag activado, O
        # - VPN dice estar conectada pero NO hay proceso real (modo demo simulado)
        is_demo_or_no_vpn = vpn_service.demo_mode or (vpn_service.vpn_connected and not vpn_service.current_vpn_process)
        
        # Si el gateway está OK (GREEN), resolver alarmas activas automáticamente
        if status == GatewayStatus.GREEN:
            active_alarms = db.query(Alarm).filter(
                Alarm.gateway_id == gateway.id,
                Alarm.status == AlarmStatus.ACTIVE
            ).all()
            
            for alarm in active_alarms:
                alarm.status = AlarmStatus.RESOLVED
                alarm.resolved_at = datetime.utcnow()
                alarm.active_duration_minutes = int(
                    (alarm.resolved_at - alarm.created_at).total_seconds() / 60
                )
                alarm.observations = "Resuelta automáticamente - Gateway recuperado"
                logger.info(f"Alarma {alarm.id} resuelta automáticamente (gateway recuperado)")
            
            db.commit()
            return
        
        # En modo DEMO, NO crear alarmas (son falsos positivos)
        if is_demo_or_no_vpn:
            logger.info(f"Modo DEMO activo - NO se crea alarma para {gateway.ip} ({description})")
            # Resolver cualquier alarma existente de este gateway (falsos positivos anteriores)
            active_alarms = db.query(Alarm).filter(
                Alarm.gateway_id == gateway.id,
                Alarm.status == AlarmStatus.ACTIVE
            ).all()
            for alarm in active_alarms:
                alarm.status = AlarmStatus.RESOLVED
                alarm.resolved_at = datetime.utcnow()
                alarm.observations = "Resuelta - Modo DEMO (sin VPN real)"
                logger.info(f"Alarma falsa {alarm.id} resuelta (modo DEMO)")
            db.commit()
            return
        
        # Crear alarma si es necesario (solo con VPN real)
        if alarm_type and status in [GatewayStatus.RED, GatewayStatus.YELLOW]:
            await self.create_or_update_alarm(
                db=db,
                plant_id=gateway.plant_id,
                gateway_id=gateway.id,
                alarm_type=alarm_type,
                severity="critical" if status == GatewayStatus.RED else "high",
                description=description,
                gateway_ip=gateway.ip
            )
    
    async def check_and_create_card_alarms(self, db: Session, card: Card):
        """
        Verifica estado de tarjeta y crea alarmas necesarias
        """
        status, alarm_type = self.analyze_card_status(card)
        
        # Actualizar estado de la tarjeta
        card.status = status
        card.updated_at = datetime.utcnow()
        db.commit()
        
        # Crear alarma si es necesario
        if alarm_type and status == CardStatus.RED:
            gateway = db.query(Gateway).filter(Gateway.id == card.gateway_id).first()
            if gateway:
                await self.create_or_update_alarm(
                    db=db,
                    plant_id=gateway.plant_id,
                    gateway_id=gateway.id,
                    card_id=card.id,
                    alarm_type=alarm_type,
                    severity="critical",
                    description=f"Tarjeta {card.modbus_id} - {alarm_type}",
                    gateway_ip=gateway.ip
                )
    
    async def create_or_update_alarm(
        self,
        db: Session,
        plant_id: int,
        alarm_type: str,
        severity: str = "medium",
        description: str = None,
        gateway_id: Optional[int] = None,
        card_id: Optional[int] = None,
        gateway_ip: Optional[str] = None
    ) -> Alarm:
        """
        Crea nueva alarma o actualiza existente
        Solo envía email cuando se crea UNA NUEVA alarma
        """
        
        # Buscar alarma existente activa del mismo tipo
        existing = db.query(Alarm).filter(
            Alarm.plant_id == plant_id,
            Alarm.alarm_type == alarm_type,
            Alarm.status == AlarmStatus.ACTIVE,
            Alarm.gateway_id == gateway_id,
            Alarm.card_id == card_id
        ).first()
        
        if existing:
            logger.info(f"Alarma ya existe: {alarm_type}")
            return existing
        
        # Crear nueva alarma
        alarm = Alarm(
            plant_id=plant_id,
            gateway_id=gateway_id,
            card_id=card_id,
            gateway_ip=gateway_ip,
            alarm_type=alarm_type,
            severity=severity,
            description=description,
            status=AlarmStatus.ACTIVE,
            created_at=datetime.utcnow()
        )
        
        db.add(alarm)
        db.commit()
        db.refresh(alarm)
        
        # Enviar email SOLO cuando es nueva alarma
        try:
            await email_service.send_alarm_email(alarm)
            alarm.email_sent = True
            alarm.last_reminder = datetime.utcnow()
            db.commit()
        except Exception as e:
            logger.error(f"Error enviando email alarma: {e}")
        
        logger.info(f"Nueva alarma creada: {alarm_type} (ID {alarm.id})")
        return alarm
    
    async def resolve_alarm(self, db: Session, alarm_id: int, observations: str = None):
        """Resuelve una alarma"""
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm and alarm.status == AlarmStatus.ACTIVE:
            alarm.status = AlarmStatus.RESOLVED
            alarm.resolved_at = datetime.utcnow()
            alarm.active_duration_minutes = int(
                (alarm.resolved_at - alarm.created_at).total_seconds() / 60
            )
            if observations:
                alarm.observations = observations
            db.commit()
            logger.info(f"Alarma resuelta: {alarm_id}")
        return alarm
    
    async def check_reminders(self, db: Session) -> int:
        """
        Verifica alarmas activas y envía recordatorios cada 7 días
        Retorna número de recordatorios enviados
        """
        reminder_threshold = datetime.utcnow() - timedelta(days=settings.ALARM_REMINDER_DAYS)
        
        active_alarms = db.query(Alarm).filter(
            Alarm.status == AlarmStatus.ACTIVE,
            (Alarm.last_reminder < reminder_threshold) |
            (Alarm.last_reminder == None)
        ).all()
        
        reminders_sent = 0
        for alarm in active_alarms:
            try:
                await email_service.send_reminder_email(alarm)
                alarm.last_reminder = datetime.utcnow()
                alarm.reminder_count = (alarm.reminder_count or 0) + 1
                reminders_sent += 1
            except Exception as e:
                logger.error(f"Error enviando recordatorio alarma {alarm.id}: {e}")
        
        db.commit()
        logger.info(f"Recordatorios de alarmas enviados: {reminders_sent}")
        return reminders_sent
    
    async def get_active_alarms(self, db: Session, plant_id: Optional[int] = None) -> List[Alarm]:
        """Obtiene todas las alarmas activas"""
        query = db.query(Alarm).filter(Alarm.status == AlarmStatus.ACTIVE)
        if plant_id:
            query = query.filter(Alarm.plant_id == plant_id)
        return query.all()
    
    async def get_plant_alarms(self, db: Session, plant_id: int) -> Dict:
        """Obtiene resumen de alarmas de una planta"""
        alarms = await self.get_active_alarms(db, plant_id)
        
        return {
            "total": len(alarms),
            "critical": len([a for a in alarms if a.severity == "critical"]),
            "high": len([a for a in alarms if a.severity == "high"]),
            "medium": len([a for a in alarms if a.severity == "medium"]),
            "alarms": [
                {
                    "id": a.id,
                    "type": a.alarm_type,
                    "severity": a.severity,
                    "description": a.description,
                    "created_at": a.created_at.isoformat() if a.created_at else None
                } for a in alarms
            ]
        }

# Instancia global
alarm_detector = AlarmDetector()
