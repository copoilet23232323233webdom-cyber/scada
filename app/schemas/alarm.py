from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class AlarmBase(BaseModel):
    alarm_type: str
    description: Optional[str] = None

class AlarmResponse(AlarmBase):
    id: int
    plant_id: int
    gateway_id: Optional[int] = None
    card_id: Optional[int] = None
    gateway_ip: Optional[str] = None
    status: str
    severity: Optional[str] = "medium"
    acknowledged_at: Optional[datetime] = None
    email_sent: bool = False
    last_reminder: Optional[datetime] = None
    reminder_count: int = 0
    created_at: datetime
    resolved_at: Optional[datetime] = None
    active_duration_minutes: int = 0
    observations: Optional[str] = None

    class Config:
        from_attributes = True

class AlarmCreate(AlarmBase):
    plant_id: int
    gateway_id: Optional[int] = None
    card_id: Optional[int] = None
    gateway_ip: Optional[str] = None

class AlarmListResponse(BaseModel):
    alarms: List[AlarmResponse]
    total: int
    page: int
    page_size: int
