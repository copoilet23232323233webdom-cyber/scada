from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean, Float, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum

class CardStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
    DISABLED = "disabled"

class Card(Base):
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    gateway_id = Column(Integer, ForeignKey("gateways.id"), nullable=False)
    modbus_id = Column(Integer, nullable=False)
    status = Column(String, default=CardStatus.UNKNOWN)  # green, yellow, red, unknown, maintenance, disabled
    communication_ok = Column(Boolean, default=False)
    sec_alarm = Column(Boolean, default=False)
    overvoltage_alarm = Column(Boolean, default=False)
    lora_ok = Column(Boolean, default=False)
    communication_alarm = Column(Boolean, default=False)
    maintenance_mode = Column(Boolean, default=False)
    disabled = Column(Boolean, default=False)
    voltage = Column(Float, nullable=True)
    response_time_ms = Column(Float, nullable=True)
    last_contact = Column(DateTime, nullable=True)
    consecutive_errors = Column(Integer, default=0)
    last_error_message = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    gateway = relationship("Gateway", back_populates="cards")
    alarms = relationship("Alarm", back_populates="card", cascade="all, delete-orphan")
