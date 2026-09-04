from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Scan(Base):
    __tablename__ = "scans"
    
    id = Column(Integer, primary_key=True, index=True)
    gateway_id = Column(Integer, ForeignKey("gateways.id"), nullable=False)
    scan_number = Column(Integer, nullable=False)
    status = Column(String, nullable=False)
    response_time = Column(Float, nullable=True)
    lora_ok = Column(Boolean, default=False)
    total_cards = Column(Integer, default=0)
    active_cards = Column(Integer, default=0)
    failed_cards = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    scan_data = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    gateway = relationship("Gateway", back_populates="scans")
