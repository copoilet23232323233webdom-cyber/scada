"""
API Endpoints para gestión de VPN.
Conectar/desconectar/reconectar, estado y diagnóstico del cliente VPN.
"""


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_admin
from app.core.database import get_db
from app.models.gateway import Gateway
from app.models.plant import Plant
from app.models.user import User
from app.services.vpn_service_v2 import resolve_plant_vpn_file, vpn_service

router = APIRouter()


def _plant_targets(db: Session, plant: Plant):
    """IPs de gateway y subredes de la planta para conectar y verificar el túnel."""
    gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
    ips = [gw.ip for gw in gateways if gw.ip]
    routes = sorted({
        '.'.join(ip.split('.')[:3]) + '.0/24' for ip in ips if len(ip.split('.')) == 4
    })
    return routes or None, ips


def _resolve_plant(db: Session, plant_name: str) -> Plant:
    plant = db.query(Plant).filter(Plant.name == plant_name).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    return plant


def _vpn_file(plant: Plant) -> str:
    vpn_file = resolve_plant_vpn_file(plant.path, plant.name)
    if not vpn_file:
        raise HTTPException(status_code=400, detail="Archivo vpn.txt no encontrado en la planta")
    return vpn_file


@router.get("/status")
async def get_vpn_status(current_user: User = Depends(get_current_user)):
    """Estado actual de la VPN"""
    return {
        "connected": vpn_service.vpn_connected,
        "current_plant": vpn_service.connected_plant(),
        "uptime_seconds": vpn_service.get_connection_uptime(),
        "method": vpn_service.current_method,
        "available_methods": vpn_service.available_vpn_methods,
    }


@router.get("/diagnostics")
async def get_vpn_diagnostics(current_user: User = Depends(get_current_user)):
    """Diagnóstico completo: clientes detectados, salud del túnel y último error."""
    return vpn_service.get_diagnostics()


@router.post("/health-check")
async def vpn_health_check(current_user: User = Depends(require_admin)):
    """Comprueba en el momento si el túnel alcanza los gateways."""
    healthy = await vpn_service.verify_tunnel(timeout=8)
    return {"healthy": healthy, "plant": vpn_service.connected_plant()}


@router.post("/connect")
async def connect_vpn(
    plant_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Conecta la VPN de una planta"""
    plant = _resolve_plant(db, plant_name)
    routes, targets = _plant_targets(db, plant)

    # force: una acción manual del usuario ignora el enfriamiento tras un fallo.
    success = await vpn_service.connect_vpn(_vpn_file(plant), plant.name, routes, targets, force=True)

    return {
        "success": success,
        "plant_name": plant.name,
        "method": vpn_service.current_method,
        "status": "connected" if success else "error",
        "error": None if success else vpn_service.last_error,
    }


@router.post("/reconnect")
async def reconnect_vpn(
    plant_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Fuerza una reconexión limpia (desconecta y vuelve a conectar)."""
    plant = _resolve_plant(db, plant_name)
    routes, targets = _plant_targets(db, plant)

    await vpn_service.disconnect_vpn()
    success = await vpn_service.connect_vpn(_vpn_file(plant), plant.name, routes, targets, force=True)

    return {
        "success": success,
        "plant_name": plant.name,
        "method": vpn_service.current_method,
        "error": None if success else vpn_service.last_error,
    }


@router.post("/disconnect")
async def disconnect_vpn(current_user: User = Depends(require_admin)):
    """Desconecta la VPN actual"""
    success = await vpn_service.disconnect_vpn()
    return {
        "success": success,
        "status": "disconnected" if success else "error"
    }
