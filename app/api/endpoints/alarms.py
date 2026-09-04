from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.alarm import Alarm
from app.models.plant import Plant
from app.schemas.alarm import AlarmResponse, AlarmListResponse
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=AlarmListResponse)
async def get_alarms(
    status: Optional[str] = None,
    plant_id: Optional[int] = None,
    alarm_type: Optional[str] = None,
    search: Optional[str] = None,
    page: int = Query(1, ge=1, description="Número de página"),
    page_size: int = Query(20, ge=1, le=100, description="Elementos por página"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Alarm)
    
    if status:
        query = query.filter(Alarm.status == status)
    
    if plant_id:
        query = query.filter(Alarm.plant_id == plant_id)
    
    if alarm_type:
        query = query.filter(Alarm.alarm_type == alarm_type)
    
    if search:
        search_filter = f"%{search}%"
        query = query.filter(
            Alarm.description.ilike(search_filter) |
            Alarm.gateway_ip.ilike(search_filter) |
            Alarm.alarm_type.ilike(search_filter)
        )
    
    if current_user.role != "admin":
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        plant_ids = [p.id for p in db.query(Plant).filter(Plant.name.in_(assigned)).all()]
        query = query.filter(Alarm.plant_id.in_(plant_ids))
    
    # Contar total
    total = query.count()
    
    # Paginar
    offset = (page - 1) * page_size
    alarms = query.order_by(Alarm.created_at.desc()).offset(offset).limit(page_size).all()
    
    return AlarmListResponse(
        alarms=alarms,
        total=total,
        page=page,
        page_size=page_size
    )

@router.get("/{alarm_id}", response_model=AlarmResponse)
async def get_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarma no encontrada")
    
    return alarm

@router.post("/{alarm_id}/resolve", response_model=AlarmResponse)
async def resolve_alarm(
    alarm_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
    
    if not alarm:
        raise HTTPException(status_code=404, detail="Alarma no encontrada")
    
    alarm.status = "resolved"
    from datetime import datetime
    alarm.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(alarm)
    
    return alarm
