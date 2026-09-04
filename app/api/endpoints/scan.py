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

    # Si ya hay un escaneo en progreso, esperar hasta 60s a que termine
    if scan_service.scanning:
        logger.info(f"Escaneo en progreso, esperando hasta 60s para escanear {plant.name}...")
        espera = 0
        while scan_service.scanning and espera < 60:
            await asyncio.sleep(2)
            espera += 2
        if scan_service.scanning:
            raise HTTPException(status_code=409, detail="Timeout esperando escaneo actual")
        logger.info(f"Escaneo anterior terminó, iniciando escaneo manual de {plant.name}")

    asyncio.create_task(_scan_with_scheduler_pause(scan_service.scan_plant(plant)))
    logger.info(f"Escaneo manual iniciado para {plant.name} (scheduler pausado)")

    return {
        "success": True,
        "message": f"Escaneo iniciado para {plant.name}",
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
