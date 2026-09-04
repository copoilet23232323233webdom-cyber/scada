from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
import os
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.alarm import Alarm
from app.schemas.plant import PlantResponse, PlantCreate, VPNConfigSchema
from app.models.user import User
from app.services.vpn_config_writer import VPNConfigError, read_plant_vpn_masked, write_plant_vpn
from app.services.vpn_service_v2 import resolve_plant_vpn_file, vpn_service

router = APIRouter()

@router.get("/", response_model=List[PlantResponse])
async def get_plants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "admin":
        plants = db.query(Plant).all()
    else:
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        plants = db.query(Plant).filter(Plant.name.in_(assigned)).all()
    
    result = []
    for plant in plants:
        gateways_count = db.query(Gateway).filter(Gateway.plant_id == plant.id).count()
        active_alarms = db.query(Alarm).filter(
            Alarm.plant_id == plant.id,
            Alarm.status == "active"
        ).count()
        
        # Calcular total de tarjetas sumando de todos los gateways
        gateway_ids = [g.id for g in db.query(Gateway.id).filter(Gateway.plant_id == plant.id).all()]
        total_cards = db.query(Card).filter(Card.gateway_id.in_(gateway_ids)).count() if gateway_ids else 0
        
        plant_dict = {
            "id": plant.id,
            "name": plant.name,
            "path": plant.path,
            "status": plant.status,
            "vpn_status": plant.vpn_status or "disconnected",
            "response_time_ms": plant.response_time_ms,
            "maintenance_mode": plant.maintenance_mode or False,
            "last_scan": plant.last_scan,
            "last_vpn_connection": plant.last_vpn_connection,
            "client_id": plant.client_id,
            "created_at": plant.created_at,
            "updated_at": plant.updated_at,
            "gateways_count": gateways_count,
            "total_cards": total_cards,
            "active_alarms": active_alarms
        }
        result.append(PlantResponse(**plant_dict))
    
    return result

@router.post("/", response_model=PlantResponse, status_code=201)
async def create_plant(
    data: PlantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing = db.query(Plant).filter(Plant.name == data.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe una planta con ese nombre")
    
    if data.name != os.path.basename(data.name.replace("\\", "/")) or data.name in (".", ".."):
        raise HTTPException(status_code=400, detail="Nombre de planta no válido")

    plant_path = os.path.normpath(f"plants/{data.name}")
    os.makedirs(plant_path, exist_ok=True)
    
    if data.vpn:
        try:
            write_plant_vpn(plant_path, data.vpn)
        except VPNConfigError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    plant = Plant(name=data.name, path=os.path.abspath(plant_path), client_id=data.client_id)
    db.add(plant)
    db.flush()
    
    for gw in data.gateways:
        g = Gateway(plant_id=plant.id, ip=gw.ip, id_start=gw.id_start, id_end=gw.id_end)
        db.add(g)
    
    db.commit()
    db.refresh(plant)
    return plant

@router.get("/{plant_id}", response_model=PlantResponse)
async def get_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    
    if current_user.role != "admin":
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        if plant.name not in assigned:
            raise HTTPException(status_code=403, detail="Sin acceso a esta planta")
    
    gateways_count = db.query(Gateway).filter(Gateway.plant_id == plant.id).count()
    active_alarms = db.query(Alarm).filter(
        Alarm.plant_id == plant.id,
        Alarm.status == "active"
    ).count()
    
    # Calcular total de tarjetas
    gateway_ids = [g.id for g in db.query(Gateway.id).filter(Gateway.plant_id == plant.id).all()]
    total_cards = db.query(Card).filter(Card.gateway_id.in_(gateway_ids)).count() if gateway_ids else 0
    
    return PlantResponse(
        id=plant.id,
        name=plant.name,
        path=plant.path,
        status=plant.status,
        vpn_status=plant.vpn_status or "disconnected",
        response_time_ms=plant.response_time_ms,
        maintenance_mode=plant.maintenance_mode or False,
        last_scan=plant.last_scan,
        last_vpn_connection=plant.last_vpn_connection,
        client_id=plant.client_id,
        created_at=plant.created_at,
        updated_at=plant.updated_at,
        gateways_count=gateways_count,
        total_cards=total_cards,
        active_alarms=active_alarms
    )


@router.put("/{plant_id}", response_model=PlantResponse)
async def update_plant(
    plant_id: int,
    plant_data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    if "name" in plant_data:
        plant.name = plant_data["name"]
    if "client_id" in plant_data:
        plant.client_id = plant_data["client_id"]
    if "maintenance_mode" in plant_data:
        plant.maintenance_mode = plant_data["maintenance_mode"]

    db.commit()
    db.refresh(plant)

    gateways_count = db.query(Gateway).filter(Gateway.plant_id == plant.id).count()
    active_alarms = db.query(Alarm).filter(
        Alarm.plant_id == plant.id,
        Alarm.status == "active"
    ).count()
    gateway_ids = [g.id for g in db.query(Gateway.id).filter(Gateway.plant_id == plant.id).all()]
    total_cards = db.query(Card).filter(Card.gateway_id.in_(gateway_ids)).count() if gateway_ids else 0

    return PlantResponse(
        id=plant.id,
        name=plant.name,
        path=plant.path,
        status=plant.status,
        vpn_status=plant.vpn_status or "disconnected",
        response_time_ms=plant.response_time_ms,
        maintenance_mode=plant.maintenance_mode or False,
        last_scan=plant.last_scan,
        last_vpn_connection=plant.last_vpn_connection,
        client_id=plant.client_id,
        created_at=plant.created_at,
        updated_at=plant.updated_at,
        gateways_count=gateways_count,
        total_cards=total_cards,
        active_alarms=active_alarms
    )


def _plant_dir(plant: Plant) -> str:
    """Carpeta local de la planta (la ruta de la BD puede ser de otra máquina)."""
    if plant.path and os.path.isdir(plant.path):
        return plant.path
    return os.path.normpath(os.path.join("plants", plant.name))


@router.get("/{plant_id}/vpn")
async def get_plant_vpn(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Configuración VPN de la planta, con las contraseñas enmascaradas."""
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    vpn_file = resolve_plant_vpn_file(plant.path, plant.name)
    plant_dir = _plant_dir(plant)
    ovpn_files = sorted(
        f for f in os.listdir(plant_dir)
        if f.lower().endswith('.ovpn')
    ) if os.path.isdir(plant_dir) else []

    return {
        "configured": bool(vpn_file),
        "directory": plant_dir,
        "ovpn_files": ovpn_files,
        "config": read_plant_vpn_masked(vpn_file) if vpn_file else {},
    }


@router.put("/{plant_id}/vpn")
async def update_plant_vpn(
    plant_id: int,
    vpn: VPNConfigSchema,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Reescribe el vpn.txt de la planta (y guarda el .ovpn subido, si lo hay)."""
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    plant_dir = _plant_dir(plant)
    try:
        write_plant_vpn(plant_dir, vpn)
    except VPNConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if plant.path != os.path.abspath(plant_dir):
        plant.path = os.path.abspath(plant_dir)
        db.commit()

    return {"success": True, "config": read_plant_vpn_masked(os.path.join(plant_dir, "vpn.txt"))}


@router.post("/{plant_id}/vpn/test")
async def test_plant_vpn(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Intenta conectar la VPN de la planta y comprobar que alcanza sus gateways."""
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    vpn_file = resolve_plant_vpn_file(plant.path, plant.name)
    if not vpn_file:
        raise HTTPException(status_code=400, detail="La planta no tiene vpn.txt configurado")

    ips = [gw.ip for gw in db.query(Gateway).filter(Gateway.plant_id == plant.id).all() if gw.ip]
    routes = sorted({
        '.'.join(ip.split('.')[:3]) + '.0/24' for ip in ips if len(ip.split('.')) == 4
    })
    success = await vpn_service.connect_vpn(vpn_file, plant.name, routes or None, ips)
    return {
        "success": success,
        "method": vpn_service.current_method,
        "error": None if success else vpn_service.last_error,
        "gateways_probed": ips,
    }


@router.delete("/{plant_id}")
async def delete_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    db.delete(plant)
    db.commit()
    return {"success": True, "message": f"Planta {plant.name} eliminada"}
