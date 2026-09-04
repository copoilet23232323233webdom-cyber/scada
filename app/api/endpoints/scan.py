import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.plant import Plant
from app.services.scan_service_v2 import scan_service
from app.tasks.scheduler_v2 import scheduler
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter()

async def _wait_for_free_scanner(plant_name: str, timeout: float = 120.0) -> bool:
    """Espera en segundo plano a que acabe el escaneo en curso."""
    espera = 0.0
    while scan_service.scanning and espera < timeout:
        await asyncio.sleep(1)
        espera += 1
    if scan_service.scanning:
        logger.warning(f"Escaneo de {plant_name} descartado: el anterior sigue en curso")
        return False
    return True


async def _scan_with_scheduler_pause(scan_coro):
    """
    Pausa el scheduler, ejecuta el escaneo manual, y reanuda el scheduler al terminar.
    Marca el escaneo en scan_service para que ni el scheduler ni el modo AUTO
    lancen otro escaneo en paralelo (competencia que colgaba la VPN).
    """
    await scheduler.pause_for_action()
    scan_service.begin_scan()
    try:
        await scan_coro
    finally:
        scan_service.end_scan()
        await scheduler.resume()

@router.post("/plant/{plant_id}")
async def scan_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")

    queued = scan_service.scanning
    db.expunge(plant)

    async def _run():
        # Si hay otro escaneo en curso se espera aqui, no en la peticion HTTP:
        # antes la pantalla se quedaba cargando hasta un minuto.
        if not await _wait_for_free_scanner(plant.name):
            return
        await _scan_with_scheduler_pause(scan_service.scan_plant(plant))

    asyncio.create_task(_run())
    logger.info(f"Escaneo manual {'encolado' if queued else 'iniciado'} para {plant.name}")

    return {
        "success": True,
        "queued": queued,
        "message": (
            f"Escaneo de {plant.name} en cola (hay otro escaneo en curso)"
            if queued else f"Escaneo iniciado para {plant.name}"
        ),
        "plant_name": plant.name
    }

@router.post("/all")
async def scan_all_plants(
    current_user: User = Depends(require_admin)
):
    """Inicia el modo AUTO: recorre TODAS las plantas en bucle continuo
    sin parar, hasta que el usuario llame a /api/scan/stop."""
    if scan_service.is_auto_loop_running():
        raise HTTPException(status_code=409, detail="El modo AUTO ya está en marcha")

    started = await scan_service.start_manual_loop()

    return {
        "success": started,
        "message": "Modo AUTO iniciado (recorriendo todas las plantas en bucle)"
    }

@router.post("/stop")
async def stop_auto_scan(
    current_user: User = Depends(require_admin)
):
    """Detiene el modo AUTO. El bucle para al terminar la planta actual."""
    if not scan_service.is_auto_loop_running():
        return {"success": True, "message": "El modo AUTO no está activo"}

    scan_service.stop_manual_loop()
    return {"success": True, "message": "Modo AUTO detenido"}

@router.get("/status")
async def scan_status(
    current_user: User = Depends(get_current_user)
):
    return {
        "scanning": scan_service.scanning,
        "auto_loop": scan_service.is_auto_loop_running(),
        "current_plant": scan_service.current_plant_name,
        "scheduler_paused": scheduler.paused
    }
