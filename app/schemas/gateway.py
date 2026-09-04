from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class GatewayBase(BaseModel):
    ip: str
    firmware: Optional[str] = None
    id_start: int = 1
    id_end: int = 32

class GatewayResponse(GatewayBase):
    id: int
    plant_id: int
    status: str
    response_time_ms: Optional[float] = None
    lora_ok: bool = False
    total_cards: int = 0
    active_cards: int = 0
    failed_cards: int = 0
    consecutive_errors: int = 0
    maintenance_mode: bool = False
    last_scan: Optional[datetime] = None
    last_error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class GatewayCreate(BaseModel):
    plant_id: int
    ip: str
    id_start: int = 1
    id_end: int = 32

class GatewayUpdate(BaseModel):
    ip: Optional[str] = None
    id_start: Optional[int] = None
    id_end: Optional[int] = None
    maintenance_mode: Optional[bool] = None
