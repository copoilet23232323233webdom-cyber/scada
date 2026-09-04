from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class CardBase(BaseModel):
    modbus_id: int

class CardResponse(CardBase):
    id: int
    gateway_id: int
    status: str
    communication_ok: bool
    lora_ok: bool
    sec_alarm: bool
    overvoltage_alarm: bool
    communication_alarm: bool
    maintenance_mode: bool
    disabled: bool
    voltage: Optional[float] = None
    response_time_ms: Optional[float] = None
    consecutive_errors: int = 0
    last_error_message: Optional[str] = None
    last_contact: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class CardUpdate(BaseModel):
    maintenance_mode: Optional[bool] = None
    disabled: Optional[bool] = None
