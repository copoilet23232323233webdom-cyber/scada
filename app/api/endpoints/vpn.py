"""
API Endpoints para gestión de VPN
Permite conectar/desconectar VPN y ver estado
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.plant import Plant
from app.services.vpn_service_v2 import vpn_service
import os

router = APIRouter()

@router.get("/status")
async def get_vpn_status(
    current_user: User = Depends(get_current_user)
):
    """Obtiene estado actual de la VPN"""
    return {
        "connected": vpn_service.vpn_connected,
        "current_plant": vpn_service.current_plant_name,
        "uptime_seconds": vpn_service.get_connection_uptime(),
        "method": vpn_service.current_vpn_config.vpn_type if vpn_service.current_vpn_config else None,
        "available_methods": vpn_service.available_vpn_methods
    }

@router.post("/connect")
async def connect_vpn(
    plant_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Conecta VPN para una planta específica"""
    plant = db.query(Plant).filter(Plant.name == plant_name).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    
    vpn_file = os.path.join(plant.path, 'vpn.txt')
    if not os.path.exists(vpn_file):
        raise HTTPException(status_code=400, detail="Archivo VPN no encontrado")
    
    success = await vpn_service.connect_vpn(vpn_file, plant.name)
    
    return {
        "success": success,
        "plant_name": plant.name,
        "status": "connected" if success else "error"
    }

@router.post("/disconnect")
async def disconnect_vpn(
    current_user: User = Depends(require_admin)
):
    """Desconecta VPN actual"""
    success = await vpn_service.disconnect_vpn()
    return {
        "success": success,
        "status": "disconnected" if success else "error"
    }