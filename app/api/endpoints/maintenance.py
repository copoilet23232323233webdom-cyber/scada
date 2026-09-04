"""
API Endpoints para Modo Mantenimiento
Permite activar/desactivar mantenimiento en tarjetas y gateways
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.plant import Plant

router = APIRouter()

@router.post("/gateway/{gateway_id}")
async def set_gateway_maintenance(
    gateway_id: int,
    maintenance_mode: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Activa/desactiva modo mantenimiento en un gateway"""
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    gateway.maintenance_mode = maintenance_mode
    db.commit()
    
    return {
        "gateway_id": gateway_id,
        "maintenance_mode": maintenance_mode,
        "status": "updated"
    }

@router.post("/card/{card_id}")
async def set_card_maintenance(
    card_id: int,
    maintenance_mode: bool,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Activa/desactiva modo mantenimiento en una tarjeta"""
    card = db.query(Card).filter(Card.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    
    card.maintenance_mode = maintenance_mode
    db.commit()
    
    return {
        "card_id": card_id,
        "maintenance_mode": maintenance_mode,
        "status": "updated"
    }

@router.get("/status")
async def get_maintenance_status(
    plant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtiene elementos en modo mantenimiento"""
    result = {
        "gateways": [],
        "cards": []
    }
    
    if plant_id:
        gateways = db.query(Gateway).filter(
            Gateway.plant_id == plant_id,
            Gateway.maintenance_mode == True
        ).all()
        cards = db.query(Card).join(Gateway).filter(
            Gateway.plant_id == plant_id,
            Card.maintenance_mode == True
        ).all()
    else:
        gateways = db.query(Gateway).filter(Gateway.maintenance_mode == True).all()
        cards = db.query(Card).filter(Card.maintenance_mode == True).all()
    
    result["gateways"] = [{"id": g.id, "ip": g.ip, "plant_id": g.plant_id} for g in gateways]
    result["cards"] = [{"id": c.id, "modbus_id": c.modbus_id, "gateway_id": c.gateway_id} for c in cards]
    
    return result