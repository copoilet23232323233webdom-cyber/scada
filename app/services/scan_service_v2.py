import os
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.scan import Scan
from app.models.alarm import Alarm
from app.services.plant_discovery import plant_discovery
from app.services.modbus_service_v2 import modbus_service
from app.services.vpn_service_v2 import vpn_service
from app.services.alarm_detector_v2 import alarm_detector
from app.websocket.manager import ws_manager
from app.core.config import settings

logger = logging.getLogger(__name__)


class ScanServiceV2:
    def __init__(self):
        self.scanning = False
        self._active_scans = 0
        self.current_plant = None
        self.current_plant_name = None
        self.auto_loop_running = False
        self._loop_task = None

    def begin_scan(self):
        """Marca que hay un escaneo en curso (scheduler/AUTO no lanzarán otro en paralelo)."""
        self._active_scans += 1
        self.scanning = self._active_scans > 0

    def end_scan(self):
        """Desmarca un escaneo terminado."""
        if self._active_scans > 0:
            self._active_scans -= 1
        self.scanning = self._active_scans > 0

    async def _update_gateway_counts(self, db: Session, gateway: Gateway):
        cards = db.query(Card).filter(Card.gateway_id == gateway.id).all()
        gateway.total_cards = len(cards)
        gateway.active_cards = len([c for c in cards if c.communication_ok])
        gateway.failed_cards = len([c for c in cards if not c.communication_ok and c.status not in ('disabled', 'maintenance')])

    async def _update_plant_counts(self, db: Session, plant: Plant):
        gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
        plant.total_gateways = len(gateways)
        total_cards = 0
        for gw in gateways:
            total_cards += db.query(Card).filter(Card.gateway_id == gw.id).count()
        plant.total_cards = total_cards

    async def scan_gateway_with_retries(self, db: Session, gateway: Gateway,
                                        timeout: float = None) -> Dict:
        logger.info(f"Escaneando {gateway.ip} (IDs {gateway.id_start}-{gateway.id_end})...")

        try:
            result = await modbus_service.scan_gateway(
                gateway.ip,
                gateway.id_start,
                gateway.id_end
            )

            actual_card_count = len(result.get('cards', []))
            gateway.status = 'green' if result['success'] else 'red'
            gateway.response_time_ms = result.get('response_time')
            gateway.lora_ok = result.get('lora_ok', False)
            gateway.last_scan = datetime.utcnow()
            gateway.last_error = result.get('error')

            if result.get('error'):
                gateway.consecutive_errors += 1
            else:
                gateway.consecutive_errors = 0

            gateway.total_cards = actual_card_count
            gateway.active_cards = len([c for c in result.get('cards', []) if c.get('communication_ok')])
            gateway.failed_cards = len([c for c in result.get('cards', []) if not c.get('communication_ok')])

            db.commit()

            plant_name = self.current_plant.name if self.current_plant else "Unknown"
            await ws_manager.broadcast_scan_update(
                plant_name=plant_name,
                gateway_ip=gateway.ip,
                status=gateway.status,
                total_cards=actual_card_count,
                active_cards=gateway.active_cards,
                failed_cards=gateway.failed_cards,
                response_time_ms=result.get('response_time')
            )

            for card_data in result.get('cards', []):
                card_id = card_data['modbus_id']
                card = db.query(Card).filter(
                    Card.gateway_id == gateway.id,
                    Card.modbus_id == card_id
                ).first()

                if not card:
                    card = Card(
                        gateway_id=gateway.id,
                        modbus_id=card_id
                    )
                    db.add(card)

                card.communication_ok = card_data.get('communication_ok', False)
                card.lora_ok = card_data.get('lora_ok', False)
                card.sec_alarm = card_data.get('sec_alarm', False)
                card.overvoltage_alarm = card_data.get('overvoltage_alarm', False)
                card.voltage = card_data.get('voltage')
                card.response_time_ms = card_data.get('response_time_ms')
                card.last_contact = datetime.utcnow()

                if card_data.get('error'):
                    card.communication_alarm = True
                    card.consecutive_errors += 1
                    card.last_error_message = card_data.get('error')
                else:
                    card.communication_alarm = False
                    card.consecutive_errors = 0

                status = 'green'
                if not card.communication_ok:
                    status = 'red'
                elif card.sec_alarm or card.overvoltage_alarm:
                    status = 'yellow'
                if card.maintenance_mode:
                    status = 'maintenance'
                if card.disabled:
                    status = 'disabled'
                card.status = status

                db.add(card)

            db.commit()

            await self._save_scan_history(db, gateway, result)
            await alarm_detector.check_and_create_alarms(db, gateway)

            return result

        except Exception as e:
            logger.error(f"Error escaneando {gateway.ip}: {e}")
            gateway.status = 'red'
            gateway.last_error = str(e)
            gateway.consecutive_errors += 1
            db.commit()
            return {'success': False, 'ip': gateway.ip, 'error': str(e)}

    async def _save_scan_history(self, db: Session, gateway: Gateway, result: Dict):
        try:
            last_scan_num = db.query(Scan).filter(
                Scan.gateway_id == gateway.id
            ).order_by(Scan.scan_number.desc()).first()
            next_num = (last_scan_num.scan_number + 1) if last_scan_num else 1

            scan = Scan(
                gateway_id=gateway.id,
                scan_number=next_num,
                status='success' if result['success'] else 'error',
                response_time=result.get('response_time'),
                lora_ok=result.get('lora_ok', False),
                total_cards=result.get('total_cards', 0),
                active_cards=result.get('active_cards', 0),
                failed_cards=result.get('failed_cards', 0),
                error_message=result.get('error'),
                scan_data=str(result.get('cards', [])),
                created_at=datetime.utcnow()
            )
            db.add(scan)
            db.commit()

            old_scans = db.query(Scan).filter(
                Scan.gateway_id == gateway.id
            ).order_by(Scan.created_at.desc()).offset(5).all()
            for old_scan in old_scans:
                db.delete(old_scan)
            db.commit()

            logger.info(f"Escaneo #{next_num} guardado para {gateway.ip}")

        except Exception as e:
            logger.error(f"Error guardando historico escaneo: {e}")

    async def _finalize_plant_scan(self, db: Session, plant: Plant, successful_scans: int, total: int):
        plant.status = 'green' if successful_scans == total else 'yellow' if successful_scans > 0 else 'red'
        plant.last_scan = datetime.utcnow()
        await self._update_plant_counts(db, plant)

        active_alarms = db.query(Alarm).filter(
            Alarm.plant_id == plant.id,
            Alarm.status == 'active'
        ).count()
        plant.active_alarms = active_alarms
        db.commit()

    async def scan_plant(self, plant: Plant) -> bool:
        db = SessionLocal()
        try:
            # Re-merge plant into this session para poder guardar cambios
            plant = db.merge(plant)
            logger.info(f"=== INICIANDO ESCANEO: {plant.name} ===")
            self.current_plant = plant
            self.current_plant_name = plant.name
            plant.status = 'scanning'
            plant.updated_at = datetime.utcnow()
            db.commit()

            is_demo_mode = vpn_service.demo_mode

            await ws_manager.broadcast_plant_status({
                "plant_name": plant.name,
                "status": "scanning",
                "message": f"Iniciando escaneo de {plant.name}" + (" (DEMO)" if is_demo_mode else "")
            })

            vpn_file = os.path.join(plant.path, 'vpn.txt')
            if not os.path.exists(vpn_file):
                logger.error(f"VPN no encontrada: {vpn_file}")
                plant.status = 'red'
                plant.vpn_status = 'error'
                db.commit()
                return False

            # Compute gateway subnets for VPN routing
            all_gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
            routes = set()
            for gw in all_gateways:
                if gw.ip:
                    parts = gw.ip.split('.')
                    if len(parts) == 4:
                        routes.add(f"{parts[0]}.{parts[1]}.{parts[2]}.0/24")
            routes_list = sorted(routes) if routes else None
            gateway_ips = [gw.ip for gw in all_gateways if gw.ip]

            logger.info(f"Conectando VPN para {plant.name}...")
            if routes_list:
                logger.info(f"Rutas VPN: {routes_list}")
            await ws_manager.broadcast_plant_status({
                "plant_name": plant.name, "status": "connecting_vpn",
                "message": f"Conectando VPN {plant.name}"
            })

            if not await vpn_service.connect_vpn(vpn_file, plant.name, routes_list, gateway_ips):
                logger.error(f"VPN fallo para {plant.name}: {vpn_service.last_error}")
                plant.status = 'red'
                plant.vpn_status = 'error'
                db.commit()
                await ws_manager.broadcast_plant_status({
                    "plant_name": plant.name, "status": "red",
                    "message": f"VPN no disponible: {vpn_service.last_error or 'error desconocido'}"
                })
                return False

            plant.vpn_status = 'demo' if vpn_service.current_method == 'demo' else 'connected'
            plant.last_vpn_connection = datetime.utcnow()
            db.commit()

            # Configurar SSH transport si el tunnel es SSH
            if hasattr(vpn_service, 'ssh_transport') and vpn_service.ssh_transport:
                modbus_service.set_ssh_transport(vpn_service.ssh_transport)
                logger.info("SSH transport configurado en Modbus service")
            else:
                modbus_service.set_ssh_transport(None)

            gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
            if not gateways:
                logger.warning(f"Sin gateways para {plant.name}")
                plant.vpn_status = 'disconnected'
                db.commit()
                return False

            # connect_vpn sólo devuelve True tras comprobar que un gateway
            # responde por el túnel, así que las rutas ya están operativas.

            # Escanear TODOS los gateways de la planta EN PARALELO.
            # Así el escaneo de la planta dura lo que tarda el gateway más lento
            # (~2-3s con el fail-fast) en vez de la suma de todos (minutos).
            await ws_manager.broadcast_plant_status({
                "plant_name": plant.name, "status": "scanning",
                "progress": f"1/{len(gateways)}",
                "message": f"Escaneando {len(gateways)} gateways de {plant.name} en paralelo"
            })

            # Cada gateway usa su PROPIA sesión de BD para evitar conflictos de
            # sesión SQLAlchemy al escanear en paralelo (un commit anula otro).
            async def _scan_one(gw):
                gw_db = SessionLocal()
                try:
                    res = await self.scan_gateway_with_retries(gw_db, gw)
                    return res.get('success', False)
                finally:
                    gw_db.close()

            results = await asyncio.gather(*[_scan_one(g) for g in gateways])
            successful_scans = sum(1 for r in results if r)

            await self._finalize_plant_scan(db, plant, successful_scans, len(gateways))

            await ws_manager.broadcast_plant_status({
                "plant_name": plant.name, "status": plant.status,
                "successful_scans": successful_scans,
                "total_gateways": len(gateways),
                "active_alarms": plant.active_alarms,
                "message": f"Completado: {successful_scans}/{len(gateways)} gateways OK"
            })

            logger.info(f"Escaneo {plant.name}: {successful_scans}/{len(gateways)} OK")
            return successful_scans > 0

        except Exception as e:
            logger.error(f"Error escaneando {plant.name}: {e}")
            if plant:
                plant.status = 'red'
                db.commit()
            await ws_manager.broadcast_plant_status({
                "plant_name": plant.name,
                "status": "error",
                "message": f"Error escaneando: {str(e)}"
            })
            return False

        finally:
            # Mantener la VPN conectada para reutilizarla en el siguiente escaneo
            # (connect_vpn la reutiliza si es la misma planta, o la desconecta si cambia).
            if plant:
                plant.vpn_status = 'connected' if vpn_service.vpn_connected else 'disconnected'
                db.commit()
            db.close()

    async def scan_all_plants(self):
        if self.scanning:
            logger.warning("Escaneo ya en progreso")
            return

        self.begin_scan()
        logger.info("=== INICIANDO CICLO COMPLETO ===")

        try:
            await ws_manager.broadcast_scheduler_status({
                "status": "running", "message": "Iniciando ciclo de escaneo"
            })

            plant_discovery.sync_plants_to_db()

            db = SessionLocal()
            try:
                plants = db.query(Plant).all()
            finally:
                db.close()

            if not plants:
                logger.warning("No hay plantas")
                return

            for i, plant in enumerate(plants):
                logger.info(f"\n--- Planta {i+1}/{len(plants)}: {plant.name} ---")
                await ws_manager.broadcast_scheduler_status({
                    "status": "running", "current_plant": plant.name,
                    "plant_index": i + 1, "total_plants": len(plants),
                    "message": f"Escaneando {plant.name}"
                })
                await self.scan_plant(plant)
                await asyncio.sleep(2)

            logger.info("=== CICLO COMPLETADO ===")
            await ws_manager.broadcast_scheduler_status({
                "status": "completed", "message": "Ciclo completado",
                "total_plants": len(plants)
            })

        except Exception as e:
            logger.error(f"Error en ciclo: {e}")
        finally:
            self.end_scan()

    def is_scanning(self) -> bool:
        return self.scanning

    def is_auto_loop_running(self) -> bool:
        return self.auto_loop_running

    async def start_manual_loop(self):
        """
        Inicia el modo AUTO manual: recorre TODAS las plantas en bucle continuo,
        sin parar, hasta que el usuario llame a stop_manual_loop().
        """
        if self.auto_loop_running and self._loop_task and not self._loop_task.done():
            logger.warning("El modo AUTO ya está en marcha")
            return False

        self.auto_loop_running = True
        self._loop_task = asyncio.create_task(self._auto_loop())
        logger.info("=== MODO AUTO INICIADO (bucle continuo) ===")
        return True

    def stop_manual_loop(self):
        """
        Detiene el modo AUTO manual. El bucle termina al completar la planta actual.
        """
        self.auto_loop_running = False
        logger.info("=== MODO AUTO: seña de parada recibida ===")
        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            self._loop_task = None

    async def _auto_loop(self):
        """Bucle continuo que recorre todas las plantas sin parar."""
        try:
            while self.auto_loop_running:
                if self.scanning:
                    await asyncio.sleep(3)
                    continue
                await self.scan_all_plants()
                if self.auto_loop_running:
                    logger.info("Modo AUTO: siguiente ronda (recorriendo todas de nuevo)...")
                    await asyncio.sleep(5)
        except asyncio.CancelledError:
            logger.info("Modo AUTO cancelado")
        except Exception as e:
            logger.error(f"Error en modo AUTO: {e}")
        finally:
            self.auto_loop_running = False
            self._loop_task = None
            logger.info("=== MODO AUTO DETENIDO ===")

    def get_current_plant(self) -> Optional[Plant]:
        return self.current_plant


scan_service = ScanServiceV2()
