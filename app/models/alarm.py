from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, Boolean, Enum
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime
import enum

class AlarmType(str, enum.Enum):
    SEC = "sec"
    OVERVOLTAGE = "overvoltage"
    COMMUNICATION = "communication"
    GATEWAY_DOWN = "gateway_down"
    VPN_DOWN = "vpn_down"
    LOW_RESPONSE = "low_response"
    CARD_TIMEOUT = "card_timeout"

class AlarmStatus(str, enum.Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    ACKNOWLEDGED = "acknowledged"

class Alarm(Base):
    __tablename__ = "alarms"
    
    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    gateway_id = Column(Integer, ForeignKey("gateways.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    gateway_ip = Column(String, nullable=True)
    alarm_type = Column(String, nullable=False)  # sec, overvoltage, communication, gateway_down, vpn_down, etc
    severity = Column(String, default="medium")  # critical, high, medium, low
    description = Column(Text, nullable=True)
    status = Column(String, default=AlarmStatus.ACTIVE)  # active, resolved, acknowledged
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
    active_duration_minutes = Column(Integer, default=0)
    observations = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    last_reminder = Column(DateTime, nullable=True)
    reminder_count = Column(Integer, default=0)
    
    plant = relationship("Plant", back_populates="alarms")
    gateway = relationship("Gateway", back_populates="alarms")
    card = relationship("Card", back_populates="alarms")
