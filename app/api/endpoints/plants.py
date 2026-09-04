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
    
    plant_path = os.path.normpath(f"plants/{data.name}")
    os.makedirs(plant_path, exist_ok=True)
    
    vpn_file = os.path.join(plant_path, "vpn.txt")
    if data.vpn:
        lines = [f"VPN_TYPE={data.vpn.type}"]
        if data.vpn.type == "openvpn":
            lines.append(f"CONFIG={data.vpn.config_path or 'openvpn.ovpn'}")
            if data.vpn.username: lines.append(f"USER={data.vpn.username}")
            if data.vpn.password: lines.append(f"PASSWORD={data.vpn.password}")
            if data.vpn.key_password: lines.append(f"KEY_PASSWORD={data.vpn.key_password}")
        elif data.vpn.type == "forticlient":
            lines.append(f"SUBTYPE={data.vpn.subtype}")
            if data.vpn.vpn_name: lines.append(f"VPN_NAME={data.vpn.vpn_name}")
            if data.vpn.host: lines.append(f"HOST={data.vpn.host}")
            lines.append(f"PORT={data.vpn.port}")
            if data.vpn.username: lines.append(f"USER={data.vpn.username}")
            if data.vpn.password: lines.append(f"PASSWORD={data.vpn.password}")
            if data.vpn.subtype == "ssl":
                if data.vpn.realm: lines.append(f"REALM={data.vpn.realm}")
                if data.vpn.trusted_cert: lines.append(f"TRUSTED_CERT={data.vpn.trusted_cert}")
                lines.append(f"ALLOW_INSECURE={'true' if data.vpn.allow_insecure else 'false'}")
            elif data.vpn.subtype == "ipsec":
                if data.vpn.psk: lines.append(f"PSK={data.vpn.psk}")
                if data.vpn.private_key: lines.append(f"PRIVATE_KEY={data.vpn.private_key}")
                if data.vpn.local_id: lines.append(f"LOCAL_ID={data.vpn.local_id}")
                if data.vpn.remote_id: lines.append(f"REMOTE_ID={data.vpn.remote_id}")
                lines.append(f"IKE_VERSION={data.vpn.ike_version}")
                # IPsec Advanced: Phase 1
                lines.append(f"PHASE1_PROPOSAL={data.vpn.phase1_proposal}")
                lines.append(f"PHASE1_DH_GROUP={data.vpn.phase1_dh_group}")
                # IPsec Advanced: Phase 2
                lines.append(f"PHASE2_PROPOSAL={data.vpn.phase2_proposal}")
                lines.append(f"PHASE2_DH_GROUP={data.vpn.phase2_dh_group}")
        elif data.vpn.type == "ssh":
            if data.vpn.ssh_host: lines.append(f"SSH_HOST={data.vpn.ssh_host}")
            lines.append(f"SSH_PORT={data.vpn.ssh_port}")
            if data.vpn.ssh_username: lines.append(f"SSH_USER={data.vpn.ssh_username}")
            if data.vpn.ssh_password: lines.append(f"SSH_PASSWORD={data.vpn.ssh_password}")
            if data.vpn.ssh_key_path: lines.append(f"SSH_KEY_PATH={data.vpn.ssh_key_path}")
        with open(vpn_file, "w") as f:
            f.write("\n".join(lines) + "\n")
    
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
