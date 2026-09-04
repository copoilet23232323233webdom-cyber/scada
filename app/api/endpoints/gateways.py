from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.gateway import Gateway
from app.models.plant import Plant
from app.schemas.gateway import GatewayResponse, GatewayUpdate, GatewayCreate
from app.models.user import User

router = APIRouter()

@router.get("/plant/{plant_id}", response_model=List[GatewayResponse])
async def get_gateways_by_plant(
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
    
    gateways = db.query(Gateway).filter(Gateway.plant_id == plant_id).all()
    return gateways

@router.get("/{gateway_id}", response_model=GatewayResponse)
async def get_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    return gateway

@router.post("/", response_model=GatewayResponse)
async def create_gateway(
    data: GatewayCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    plant = db.query(Plant).filter(Plant.id == data.plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    existing = db.query(Gateway).filter(Gateway.ip == data.ip).first()
    if existing:
        raise HTTPException(status_code=400, detail="Ya existe un gateway con esa IP")
    gateway = Gateway(**data.dict())
    db.add(gateway)
    db.commit()
    db.refresh(gateway)
    return gateway

@router.delete("/{gateway_id}")
async def delete_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    db.delete(gateway)
    db.commit()
    return {"detail": "Gateway eliminado"}

@router.patch("/{gateway_id}", response_model=GatewayResponse)
async def update_gateway(
    gateway_id: int,
    data: GatewayUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    for field, value in data.dict(exclude_unset=True).items():
        setattr(gateway, field, value)
    db.commit()
    db.refresh(gateway)
    return gateway
