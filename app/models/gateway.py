from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Float, Boolean, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum

class GatewayStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"

class Gateway(Base):
    __tablename__ = "gateways"
    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"))
    ip = Column(String(50), unique=True, index=True)
    firmware = Column(String, nullable=True)
    id_start = Column(Integer, default=1)
    id_end = Column(Integer, default=32)
    status = Column(String, default=GatewayStatus.UNKNOWN)  # green, yellow, red, unknown
    response_time_ms = Column(Float, nullable=True)
    lora_ok = Column(Boolean, default=False)
    total_cards = Column(Integer, default=0)
    active_cards = Column(Integer, default=0)
    failed_cards = Column(Integer, default=0)
    consecutive_errors = Column(Integer, default=0)
    maintenance_mode = Column(Boolean, default=False)
    last_scan = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    plant = relationship("Plant", back_populates="gateways")
    cards = relationship("Card", back_populates="gateway", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="gateway", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="gateway")
