import os
import logging
from app.core.database import SessionLocal
from app.models.plant import Plant
from app.models.gateway import Gateway

logger = logging.getLogger(__name__)

class PlantDiscovery:
    def __init__(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.plants_dir = os.path.join(base_dir, 'plants')
        logger.info(f"Directorio de plantas: {self.plants_dir}")

    def discover_plants(self):
        plants = []
        if not os.path.exists(self.plants_dir):
            return plants
        for item in os.listdir(self.plants_dir):
            plant_path = os.path.join(self.plants_dir, item)
            if os.path.isdir(plant_path):
                if os.path.exists(os.path.join(plant_path, 'vpn.txt')) and os.path.exists(os.path.join(plant_path, 'ips.txt')):
                    plants.append({'name': item, 'path': plant_path})
        return plants

    def parse_ips_file(self, ips_file: str):
        gateways = []
        try:
            with open(ips_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    if ':' in line:
                        ip_part, range_part = line.split(':', 1)
                        ip = ip_part.strip()
                        if '-' in range_part:
                            id_start, id_end = map(int, range_part.split('-', 1))
                        else:
                            id_start = id_end = int(range_part.strip())
                        gateways.append({'ip': ip, 'id_start': id_start, 'id_end': id_end})
        except Exception as e:
            logger.error(f"Error parseando {ips_file}: {e}")
        return gateways

    def sync_plants_to_db(self):
        db = SessionLocal()
        try:
            for plant_data in self.discover_plants():
                plant = db.query(Plant).filter(Plant.name == plant_data['name']).first()
                if not plant:
                    plant = Plant(name=plant_data['name'], path=plant_data['path'], status='unknown')
                    db.add(plant)
                    db.commit()
                    db.refresh(plant)

                # Obtener IPs actuales del archivo
                current_ips = {gw['ip']: gw for gw in self.parse_ips_file(os.path.join(plant_data['path'], 'ips.txt'))}

                # Obtener gateways existentes en BD
                existing_gateways = {gw.ip: gw for gw in db.query(Gateway).filter(Gateway.plant_id == plant.id).all()}

                # Actualizar gateways existentes o crear nuevos
                for ip, gw_data in current_ips.items():
                    if ip in existing_gateways:
                        gw = existing_gateways[ip]
                        gw.id_start = gw_data['id_start']
                        gw.id_end = gw_data['id_end']
                    else:
                        gw = Gateway(
                            plant_id=plant.id,
                            ip=ip,
                            id_start=gw_data['id_start'],
                            id_end=gw_data['id_end'],
                            status='unknown'
                        )
                        db.add(gw)
                    del existing_gateways[ip]

                # Eliminar gateways que ya no están en ips.txt
                for ip, gw in existing_gateways.items():
                    logger.warning(f"Gateway {ip} eliminado (ya no está en ips.txt)")
                    db.delete(gw)

                db.commit()
                logger.info(f"Planta {plant_data['name']} sincronizada ({len(current_ips)} gateways)")
        except Exception as e:
            logger.error(f"Error sync: {e}")
            db.rollback()
        finally:
            db.close()

plant_discovery = PlantDiscovery()
