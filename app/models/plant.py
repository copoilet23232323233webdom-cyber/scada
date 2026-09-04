from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum

class PlantStatus(str, enum.Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"
    UNKNOWN = "unknown"
    SCANNING = "scanning"

class Plant(Base):
    __tablename__ = "plants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    path = Column(String, nullable=False)
    status = Column(String, default=PlantStatus.UNKNOWN)  # green, yellow, red, unknown, scanning
    vpn_status = Column(String, default="disconnected")  # connected, disconnected, error
    response_time_ms = Column(Integer, nullable=True)
    last_scan = Column(DateTime, nullable=True)
    last_vpn_connection = Column(DateTime, nullable=True)
    total_gateways = Column(Integer, default=0)
    total_cards = Column(Integer, default=0)
    active_alarms = Column(Integer, default=0)
    client_id = Column(String, nullable=True)
    maintenance_mode = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    gateways = relationship("Gateway", back_populates="plant", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="plant", cascade="all, delete-orphan")
