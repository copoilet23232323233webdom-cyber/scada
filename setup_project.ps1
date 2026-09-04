# Script para generar todo el proyecto Webdom Monitor
# Ejecutar: .\setup_project.ps1

$ErrorActionPreference = "Stop"

Write-Host "=== Generando proyecto Webdom Monitor ===" -ForegroundColor Green

# ============================================
# BACKEND - Archivos Python/FastAPI
# ============================================

Write-Host "Creando archivos del Backend..." -ForegroundColor Yellow

# app/__init__.py
@'
# Webdom Monitor Backend
'@ | Out-File -FilePath "app\__init__.py" -Encoding UTF8

# app/main.py
@'
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import init_db
from app.tasks.scheduler import start_scheduler, stop_scheduler
from app.api.endpoints import auth, plants, gateways, cards, alarms, users, websocket

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    scheduler_task = asyncio.create_task(start_scheduler())
    yield
    stop_scheduler()
    scheduler_task.cancel()

app = FastAPI(
    title="Webdom Monitor",
    description="Plataforma de Monitorización Remota para Webdom Gateway",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(plants.router, prefix="/api/plants", tags=["plants"])
app.include_router(gateways.router, prefix="/api/gateways", tags=["gateways"])
app.include_router(cards.router, prefix="/api/cards", tags=["cards"])
app.include_router(alarms.router, prefix="/api/alarms", tags=["alarms"])
app.include_router(users.router, prefix="/api/users", tags=["users"])
app.include_router(websocket.router, prefix="/api/ws", tags=["websocket"])

@app.get("/")
async def root():
    return {"message": "Webdom Monitor API", "version": "1.0.0"}

@app.get("/health")
async def health():
    return {"status": "healthy"}
'@ | Out-File -FilePath "app\main.py" -Encoding UTF8

# app/core/__init__.py
@'
'@ | Out-File -FilePath "app\core\__init__.py" -Encoding UTF8

# app/core/config.py
@'
from pydantic_settings import BaseSettings
from typing import List

class Settings(BaseSettings):
    APP_NAME: str = "Webdom Monitor"
    DATABASE_URL: str = "sqlite:///./webdom_monitor.db"
    SECRET_KEY: str = "your-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440
    CORS_ORIGINS: List[str] = ["http://localhost:5173", "http://localhost:3000"]
    
    SMTP_SERVER: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = "webdomreports@gmail.com"
    SMTP_PASSWORD: str = ""
    
    SCAN_INTERVAL_SECONDS: int = 300
    SCAN_RETRIES: int = 5
    ALARM_REMINDER_DAYS: int = 7
    
    MODBUS_PORT: int = 502
    MODBUS_TIMEOUT: float = 5.0
    
    VPN_EXECUTABLE_OPENVPN: str = "C:\\Program Files\\OpenVPN\\bin\\openvpn.exe"
    VPN_EXECUTABLE_FORTICLIENT: str = "C:\\Program Files\\Fortinet\\FortiClient\\FortiClient.exe"
    
    class Config:
        env_file = ".env"

settings = Settings()
'@ | Out-File -FilePath "app\core\config.py" -Encoding UTF8

# app/core/database.py
@'
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def init_db():
    from app.models import plant, gateway, card, alarm, user, scan
    Base.metadata.create_all(bind=engine)
'@ | Out-File -FilePath "app\core\database.py" -Encoding UTF8

# app/core/security.py
@'
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt

def decode_access_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None
'@ | Out-File -FilePath "app\core\security.py" -Encoding UTF8

# app/models/__init__.py
@'
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.alarm import Alarm
from app.models.user import User
from app.models.scan import Scan
'@ | Out-File -FilePath "app\models\__init__.py" -Encoding UTF8

# app/models/plant.py
@'
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Plant(Base):
    __tablename__ = "plants"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True, nullable=False)
    path = Column(String, nullable=False)
    status = Column(String, default="unknown")
    last_scan = Column(DateTime, default=datetime.utcnow)
    last_vpn_connection = Column(DateTime, nullable=True)
    client_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    gateways = relationship("Gateway", back_populates="plant", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="plant", cascade="all, delete-orphan")
'@ | Out-File -FilePath "app\models\plant.py" -Encoding UTF8

# app/models/gateway.py
@'
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Gateway(Base):
    __tablename__ = "gateways"
    
    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    ip = Column(String, nullable=False)
    status = Column(String, default="unknown")
    firmware = Column(String, nullable=True)
    response_time = Column(Float, nullable=True)
    total_cards = Column(Integer, default=0)
    active_cards = Column(Integer, default=0)
    failed_cards = Column(Integer, default=0)
    lora_ok = Column(Boolean, default=False)
    last_scan = Column(DateTime, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    plant = relationship("Plant", back_populates="gateways")
    cards = relationship("Card", back_populates="gateway", cascade="all, delete-orphan")
    scans = relationship("Scan", back_populates="gateway", cascade="all, delete-orphan")
    alarms = relationship("Alarm", back_populates="gateway", cascade="all, delete-orphan")
'@ | Out-File -FilePath "app\models\gateway.py" -Encoding UTF8

# app/models/card.py
@'
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Card(Base):
    __tablename__ = "cards"
    
    id = Column(Integer, primary_key=True, index=True)
    gateway_id = Column(Integer, ForeignKey("gateways.id"), nullable=False)
    modbus_id = Column(Integer, nullable=False)
    status = Column(String, default="unknown")
    communication_ok = Column(Boolean, default=False)
    sec_alarm = Column(Boolean, default=False)
    overvoltage_alarm = Column(Boolean, default=False)
    communication_alarm = Column(Boolean, default=False)
    maintenance_mode = Column(Boolean, default=False)
    disabled = Column(Boolean, default=False)
    last_contact = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    gateway = relationship("Gateway", back_populates="cards")
    alarms = relationship("Alarm", back_populates="card", cascade="all, delete-orphan")
'@ | Out-File -FilePath "app\models\card.py" -Encoding UTF8

# app/models/alarm.py
@'
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from app.core.database import Base
from datetime import datetime

class Alarm(Base):
    __tablename__ = "alarms"
    
    id = Column(Integer, primary_key=True, index=True)
    plant_id = Column(Integer, ForeignKey("plants.id"), nullable=False)
    gateway_id = Column(Integer, ForeignKey("gateways.id"), nullable=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=True)
    gateway_ip = Column(String, nullable=True)
    alarm_type = Column(String, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String, default="active")
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    active_duration_minutes = Column(Integer, default=0)
    observations = Column(Text, nullable=True)
    email_sent = Column(Boolean, default=False)
    last_reminder = Column(DateTime, nullable=True)
    
    plant = relationship("Plant", back_populates="alarms")
    gateway = relationship("Gateway", back_populates="alarms")
    card = relationship("Card", back_populates="alarms")
'@ | Out-File -FilePath "app\models\alarm.py" -Encoding UTF8

# app/models/user.py
@'
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from app.core.database import Base
from datetime import datetime

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True, nullable=False)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    full_name = Column(String, nullable=True)
    role = Column(String, default="client")
    assigned_plants = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
'@ | Out-File -FilePath "app\models\user.py" -Encoding UTF8

# app/models/scan.py
@'
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
'@ | Out-File -FilePath "app\models\scan.py" -Encoding UTF8

# app/schemas/__init__.py
@'
'@ | Out-File -FilePath "app\schemas\__init__.py" -Encoding UTF8

# app/schemas/plant.py
@'
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class PlantBase(BaseModel):
    name: str
    path: str
    client_id: Optional[str] = None

class PlantCreate(PlantBase):
    pass

class PlantUpdate(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None

class PlantResponse(PlantBase):
    id: int
    status: str
    last_scan: Optional[datetime]
    last_vpn_connection: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    gateways_count: int = 0
    total_cards: int = 0
    active_alarms: int = 0
    
    class Config:
        from_attributes = True

class PlantList(BaseModel):
    plants: List[PlantResponse]
    total: int
'@ | Out-File -FilePath "app\schemas\plant.py" -Encoding UTF8

# app/schemas/gateway.py
@'
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class GatewayBase(BaseModel):
    ip: str
    firmware: Optional[str] = None

class GatewayResponse(GatewayBase):
    id: int
    plant_id: int
    status: str
    response_time: Optional[float]
    total_cards: int
    active_cards: int
    failed_cards: int
    lora_ok: bool
    last_scan: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class GatewayList(BaseModel):
    gateways: List[GatewayResponse]
    total: int
'@ | Out-File -FilePath "app\schemas\gateway.py" -Encoding UTF8

# app/schemas/card.py
@'
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
    sec_alarm: bool
    overvoltage_alarm: bool
    communication_alarm: bool
    maintenance_mode: bool
    disabled: bool
    last_contact: Optional[datetime]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class CardUpdate(BaseModel):
    maintenance_mode: Optional[bool] = None
    disabled: Optional[bool] = None
'@ | Out-File -FilePath "app\schemas\card.py" -Encoding UTF8

# app/schemas/alarm.py
@'
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AlarmBase(BaseModel):
    alarm_type: str
    description: Optional[str] = None

class AlarmResponse(AlarmBase):
    id: int
    plant_id: int
    gateway_id: Optional[int]
    card_id: Optional[int]
    gateway_ip: Optional[str]
    status: str
    created_at: datetime
    resolved_at: Optional[datetime]
    active_duration_minutes: int
    observations: Optional[str]
    
    class Config:
        from_attributes = True

class AlarmCreate(AlarmBase):
    plant_id: int
    gateway_id: Optional[int] = None
    card_id: Optional[int] = None
    gateway_ip: Optional[str] = None
'@ | Out-File -FilePath "app\schemas\alarm.py" -Encoding UTF8

# app/schemas/user.py
@'
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime

class UserBase(BaseModel):
    username: str
    email: EmailStr
    full_name: Optional[str] = None
    role: str = "client"

class UserCreate(UserBase):
    password: str
    assigned_plants: Optional[str] = None

class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    assigned_plants: Optional[str] = None
    is_active: Optional[bool] = None

class UserResponse(UserBase):
    id: int
    is_active: bool
    assigned_plants: Optional[str]
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True
'@ | Out-File -FilePath "app\schemas\user.py" -Encoding UTF8

# app/schemas/auth.py
@'
from pydantic import BaseModel

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    username: str
    role: str
'@ | Out-File -FilePath "app\schemas\auth.py" -Encoding UTF8

# app/services/__init__.py
@'
'@ | Out-File -FilePath "app\services\__init__.py" -Encoding UTF8

# app/services/modbus_service.py
@'
import asyncio
import logging
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusException
from typing import Dict, List, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class ModbusService:
    # Registros Modbus segun documentacion Webdom
    STATUS_REGISTER = 57624
    VOLTAGE_REGISTER = 57625
    TEMPERATURE_REGISTER = 57626
    CURRENT_REGISTERS_START = 57627
    CURRENT_REGISTERS_END = 57658
    
    def __init__(self):
        self.timeout = settings.MODBUS_TIMEOUT
        self.port = settings.MODBUS_PORT
    
    async def read_gateway_status(self, ip: str) -> Optional[Dict]:
        try:
            client = ModbusTcpClient(ip, port=self.port, timeout=self.timeout)
            
            loop = asyncio.get_event_loop()
            connected = await loop.run_in_executor(None, client.connect)
            
            if not connected:
                logger.error(f"No se pudo conectar a {ip}")
                return None
            
            try:
                result = await loop.run_in_executor(
                    None, 
                    lambda: client.read_holding_registers(self.STATUS_REGISTER, 1, slave=100)
                )
                
                if result.isError():
                    logger.error(f"Error leyendo status de {ip}: {result}")
                    return None
                
                status_value = result.registers[0]
                
                lora_ok = bool(status_value & (1 << 5))
                digital_in_1 = bool(status_value & (1 << 0))
                digital_in_2 = bool(status_value & (1 << 1))
                
                return {
                    "ip": ip,
                    "status_value": status_value,
                    "lora_ok": lora_ok,
                    "digital_in_1": digital_in_1,
                    "digital_in_2": digital_in_2,
                    "success": True
                }
            finally:
                client.close()
                
        except Exception as e:
            logger.error(f"Error en read_gateway_status para {ip}: {e}")
            return None
    
    async def discover_cards(self, ip: str) -> List[Dict]:
        cards = []
        
        try:
            client = ModbusTcpClient(ip, port=self.port, timeout=self.timeout)
            
            loop = asyncio.get_event_loop()
            connected = await loop.run_in_executor(None, client.connect)
            
            if not connected:
                return cards
            
            try:
                for modbus_id in range(1, 33):
                    try:
                        result = await loop.run_in_executor(
                            None,
                            lambda mid=modbus_id: client.read_holding_registers(
                                self.STATUS_REGISTER, 1, slave=mid
                            )
                        )
                        
                        if not result.isError():
                            status_value = result.registers[0]
                            lora_ok = bool(status_value & (1 << 5))
                            
                            cards.append({
                                "modbus_id": modbus_id,
                                "status_value": status_value,
                                "lora_ok": lora_ok,
                                "communication_ok": lora_ok,
                                "active": True
                            })
                        else:
                            cards.append({
                                "modbus_id": modbus_id,
                                "status_value": None,
                                "lora_ok": False,
                                "communication_ok": False,
                                "active": False
                            })
                    except Exception as e:
                        logger.debug(f"Error leyendo tarjeta {modbus_id} en {ip}: {e}")
                        cards.append({
                            "modbus_id": modbus_id,
                            "status_value": None,
                            "lora_ok": False,
                            "communication_ok": False,
                            "active": False
                        })
            finally:
                client.close()
                
        except Exception as e:
            logger.error(f"Error en discover_cards para {ip}: {e}")
        
        return cards
    
    async def scan_gateway(self, ip: str) -> Dict:
        import time
        start_time = time.time()
        
        result = {
            "ip": ip,
            "success": False,
            "response_time": None,
            "lora_ok": False,
            "cards": [],
            "total_cards": 0,
            "active_cards": 0,
            "failed_cards": 0,
            "error": None
        }
        
        try:
            status = await self.read_gateway_status(ip)
            
            if not status or not status.get("success"):
                result["error"] = "No se pudo leer el status del gateway"
                return result
            
            result["lora_ok"] = status.get("lora_ok", False)
            
            cards = await self.discover_cards(ip)
            result["cards"] = cards
            result["total_cards"] = len(cards)
            result["active_cards"] = sum(1 for c in cards if c.get("active"))
            result["failed_cards"] = sum(1 for c in cards if not c.get("active"))
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Error escaneando gateway {ip}: {e}")
        
        result["response_time"] = time.time() - start_time
        return result

modbus_service = ModbusService()
'@ | Out-File -FilePath "app\services\modbus_service.py" -Encoding UTF8

# app/services/vpn_service.py
@'
import asyncio
import subprocess
import logging
import os
from typing import Dict, Optional
from app.core.config import settings

logger = logging.getLogger(__name__)

class VPNService:
    def __init__(self):
        self.current_vpn_process = None
        self.current_vpn_name = None
    
    def parse_vpn_config(self, vpn_file: str) -> Dict:
        config = {}
        try:
            with open(vpn_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        config[key.strip()] = value.strip()
        except Exception as e:
            logger.error(f"Error leyendo archivo VPN {vpn_file}: {e}")
        return config
    
    async def connect_openvpn(self, config: Dict, plant_name: str) -> bool:
        try:
            config_file = config.get('CONFIG')
            user = config.get('USER')
            password = config.get('PASSWORD')
            
            if not config_file or not os.path.exists(config_file):
                logger.error(f"Archivo de configuracion OpenVPN no encontrado: {config_file}")
                return False
            
            cmd = [
                settings.VPN_EXECUTABLE_OPENVPN,
                '--config', config_file
            ]
            
            if user and password:
                auth_file = f"temp_{plant_name}_auth.txt"
                with open(auth_file, 'w') as f:
                    f.write(f"{user}\n{password}\n")
                cmd.extend(['--auth-user-pass', auth_file])
            
            self.current_vpn_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.current_vpn_name = plant_name
            await asyncio.sleep(10)
            
            return True
            
        except Exception as e:
            logger.error(f"Error conectando OpenVPN para {plant_name}: {e}")
            return False
    
    async def connect_forticlient(self, config: Dict, plant_name: str) -> bool:
        try:
            vpn_name = config.get('VPN_NAME')
            host = config.get('HOST')
            user = config.get('USER')
            password = config.get('PASSWORD')
            
            if not vpn_name or not host:
                logger.error(f"Configuracion FortiClient incompleta para {plant_name}")
                return False
            
            cmd = [
                settings.VPN_EXECUTABLE_FORTICLIENT,
                'connect',
                '--name', vpn_name,
                '--host', host
            ]
            
            if user and password:
                cmd.extend(['--user', user, '--password', password])
            
            self.current_vpn_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            self.current_vpn_name = plant_name
            await asyncio.sleep(15)
            
            return True
            
        except Exception as e:
            logger.error(f"Error conectando FortiClient para {plant_name}: {e}")
            return False
    
    async def connect_vpn(self, vpn_file: str, plant_name: str) -> bool:
        config = self.parse_vpn_config(vpn_file)
        
        if not config:
            logger.error(f"No se pudo leer la configuracion VPN para {plant_name}")
            return False
        
        vpn_type = config.get('VPN_TYPE', '').lower()
        
        if vpn_type == 'openvpn':
            return await self.connect_openvpn(config, plant_name)
        elif vpn_type == 'forticlient':
            return await self.connect_forticlient(config, plant_name)
        else:
            logger.error(f"Tipo de VPN no soportado: {vpn_type}")
            return False
    
    async def disconnect_vpn(self) -> bool:
        try:
            if self.current_vpn_process:
                self.current_vpn_process.terminate()
                self.current_vpn_process.wait(timeout=10)
                self.current_vpn_process = None
                self.current_vpn_name = None
                await asyncio.sleep(5)
                return True
            return True
        except Exception as e:
            logger.error(f"Error desconectando VPN: {e}")
            try:
                if self.current_vpn_process:
                    self.current_vpn_process.kill()
            except:
                pass
            return False
    
    def is_connected(self) -> bool:
        return self.current_vpn_process is not None and self.current_vpn_process.poll() is None

vpn_service = VPNService()
'@ | Out-File -FilePath "app\services\vpn_service.py" -Encoding UTF8

# app/services/plant_discovery.py
@'
import os
import logging
from typing import List, Dict
from app.core.database import SessionLocal
from app.models.plant import Plant

logger = logging.getLogger(__name__)

class PlantDiscovery:
    def __init__(self, plants_dir: str = "plants"):
        self.plants_dir = plants_dir
    
    def discover_plants(self) -> List[Dict]:
        plants = []
        
        if not os.path.exists(self.plants_dir):
            logger.warning(f"Directorio de plantas no encontrado: {self.plants_dir}")
            return plants
        
        for plant_name in os.listdir(self.plants_dir):
            plant_path = os.path.join(self.plants_dir, plant_name)
            
            if not os.path.isdir(plant_path):
                continue
            
            ips_file = os.path.join(plant_path, "ips.txt")
            vpn_file = os.path.join(plant_path, "vpn.txt")
            
            if not os.path.exists(ips_file):
                logger.warning(f"Archivo ips.txt no encontrado para planta {plant_name}")
                continue
            
            ips = []
            try:
                with open(ips_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        ip = line.strip()
                        if ip and not ip.startswith('#'):
                            ips.append(ip)
            except Exception as e:
                logger.error(f"Error leyendo ips.txt para {plant_name}: {e}")
                continue
            
            vpn_config = None
            if os.path.exists(vpn_file):
                vpn_config = vpn_file
            
            plants.append({
                "name": plant_name,
                "path": plant_path,
                "ips": ips,
                "vpn_file": vpn_config
            })
        
        return plants
    
    def sync_plants_to_db(self) -> int:
        db = SessionLocal()
        try:
            discovered_plants = self.discover_plants()
            
            existing_plants = {p.name: p for p in db.query(Plant).all()}
            
            created = 0
            for plant_data in discovered_plants:
                plant_name = plant_data["name"]
                
                if plant_name not in existing_plants:
                    new_plant = Plant(
                        name=plant_name,
                        path=plant_data["path"],
                        status="unknown"
                    )
                    db.add(new_plant)
                    created += 1
                    logger.info(f"Nueva planta descubierta: {plant_name}")
            
            db.commit()
            return created
            
        except Exception as e:
            logger.error(f"Error sincronizando plantas: {e}")
            db.rollback()
            return 0
        finally:
            db.close()

plant_discovery = PlantDiscovery()
'@ | Out-File -FilePath "app\services\plant_discovery.py" -Encoding UTF8

# app/services/alarm_service.py
@'
import logging
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from app.models.alarm import Alarm
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.services.email_service import email_service
from app.core.config import settings

logger = logging.getLogger(__name__)

class AlarmService:
    async def create_alarm(
        self,
        db: Session,
        plant_id: int,
        alarm_type: str,
        description: str,
        gateway_id: Optional[int] = None,
        card_id: Optional[int] = None,
        gateway_ip: Optional[str] = None
    ) -> Alarm:
        
        existing = db.query(Alarm).filter(
            Alarm.plant_id == plant_id,
            Alarm.alarm_type == alarm_type,
            Alarm.gateway_id == gateway_id,
            Alarm.card_id == card_id,
            Alarm.status == "active"
        ).first()
        
        if existing:
            logger.info(f"Alarma ya existe: {alarm_type} para planta {plant_id}")
            return existing
        
        alarm = Alarm(
            plant_id=plant_id,
            gateway_id=gateway_id,
            card_id=card_id,
            gateway_ip=gateway_ip,
            alarm_type=alarm_type,
            description=description,
            status="active",
            created_at=datetime.utcnow()
        )
        
        db.add(alarm)
        db.commit()
        db.refresh(alarm)
        
        await email_service.send_alarm_email(alarm)
        alarm.email_sent = True
        alarm.last_reminder = datetime.utcnow()
        db.commit()
        
        logger.info(f"Nueva alarma creada: {alarm_type} para planta {plant_id}")
        return alarm
    
    async def resolve_alarm(self, db: Session, alarm_id: int) -> Alarm:
        alarm = db.query(Alarm).filter(Alarm.id == alarm_id).first()
        if alarm and alarm.status == "active":
            alarm.status = "resolved"
            alarm.resolved_at = datetime.utcnow()
            alarm.active_duration_minutes = int((alarm.resolved_at - alarm.created_at).total_seconds() / 60)
            db.commit()
            db.refresh(alarm)
            logger.info(f"Alarma resuelta: {alarm_id}")
        return alarm
    
    async def check_reminders(self, db: Session) -> int:
        reminder_threshold = datetime.utcnow() - timedelta(days=settings.ALARM_REMINDER_DAYS)
        
        active_alarms = db.query(Alarm).filter(
            Alarm.status == "active",
            Alarm.last_reminder < reminder_threshold
        ).all()
        
        reminders_sent = 0
        for alarm in active_alarms:
            await email_service.send_reminder_email(alarm)
            alarm.last_reminder = datetime.utcnow()
            reminders_sent += 1
        
        db.commit()
        return reminders_sent
    
    async def get_active_alarms(self, db: Session, plant_id: Optional[int] = None) -> List[Alarm]:
        query = db.query(Alarm).filter(Alarm.status == "active")
        if plant_id:
            query = query.filter(Alarm.plant_id == plant_id)
        return query.all()

alarm_service = AlarmService()
'@ | Out-File -FilePath "app\services\alarm_service.py" -Encoding UTF8

# app/services/email_service.py
@'
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from app.core.config import settings
from app.models.alarm import Alarm

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.smtp_server = settings.SMTP_SERVER
        self.smtp_port = settings.SMTP_PORT
        self.smtp_user = settings.SMTP_USER
        self.smtp_password = settings.SMTP_PASSWORD
    
    async def send_email(self, to_email: str, subject: str, body: str) -> bool:
        try:
            msg = MIMEMultipart()
            msg['From'] = self.smtp_user
            msg['To'] = to_email
            msg['Subject'] = subject
            
            msg.attach(MIMEText(body, 'html'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_user, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            logger.info(f"Email enviado a {to_email}: {subject}")
            return True
            
        except Exception as e:
            logger.error(f"Error enviando email: {e}")
            return False
    
    async def send_alarm_email(self, alarm: Alarm) -> bool:
        subject = f"[Webdom Monitor] ALARMA: {alarm.alarm_type}"
        
        body = f"""
        <h2>Nueva Alarma Detectada</h2>
        <table border="1" cellpadding="5">
            <tr><td><strong>Tipo de Alarma</strong></td><td>{alarm.alarm_type}</td></tr>
            <tr><td><strong>Descripcion</strong></td><td>{alarm.description or 'N/A'}</td></tr>
            <tr><td><strong>Gateway IP</strong></td><td>{alarm.gateway_ip or 'N/A'}</td></tr>
            <tr><td><strong>Fecha</strong></td><td>{alarm.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        <p>Esta alarma permanecera activa hasta que se resuelva el problema.</p>
        """
        
        return await self.send_email("webdomreports@gmail.com", subject, body)
    
    async def send_reminder_email(self, alarm: Alarm) -> bool:
        subject = f"[Webdom Monitor] RECORDATORIO: Alarma activa - {alarm.alarm_type}"
        
        days_active = (datetime.utcnow() - alarm.created_at).days
        
        body = f"""
        <h2>Recordatorio de Alarma Activa</h2>
        <p>La siguiente alarma lleva activa <strong>{days_active} dias</strong>:</p>
        <table border="1" cellpadding="5">
            <tr><td><strong>Tipo de Alarma</strong></td><td>{alarm.alarm_type}</td></tr>
            <tr><td><strong>Descripcion</strong></td><td>{alarm.description or 'N/A'}</td></tr>
            <tr><td><strong>Gateway IP</strong></td><td>{alarm.gateway_ip or 'N/A'}</td></tr>
            <tr><td><strong>Fecha de Creacion</strong></td><td>{alarm.created_at.strftime('%Y-%m-%d %H:%M:%S')}</td></tr>
        </table>
        """
        
        return await self.send_email("webdomreports@gmail.com", subject, body)

email_service = EmailService()
'@ | Out-File -FilePath "app\services\email_service.py" -Encoding UTF8

# app/services/scan_service.py
@'
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from sqlalchemy.orm import Session
from app.core.database import SessionLocal
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card
from app.models.scan import Scan
from app.services.modbus_service import modbus_service
from app.services.vpn_service import vpn_service
from app.services.alarm_service import alarm_service
from app.services.plant_discovery import plant_discovery
from app.core.config import settings

logger = logging.getLogger(__name__)

class ScanService:
    def __init__(self):
        self.scanning = False
    
    async def scan_gateway_with_retries(self, db: Session, gateway: Gateway, plant: Plant) -> Dict:
        results = []
        
        for i in range(settings.SCAN_RETRIES):
            logger.info(f"Escaneo {i+1}/{settings.SCAN_RETRIES} para gateway {gateway.ip}")
            
            scan_result = await modbus_service.scan_gateway(gateway.ip)
            results.append(scan_result)
            
            scan_record = Scan(
                gateway_id=gateway.id,
                scan_number=i+1,
                status="success" if scan_result["success"] else "error",
                response_time=scan_result.get("response_time"),
                lora_ok=scan_result.get("lora_ok", False),
                total_cards=scan_result.get("total_cards", 0),
                active_cards=scan_result.get("active_cards", 0),
                failed_cards=scan_result.get("failed_cards", 0),
                error_message=scan_result.get("error"),
                scan_data=str(scan_result)
            )
            db.add(scan_record)
            db.commit()
            
            if i < settings.SCAN_RETRIES - 1:
                await asyncio.sleep(2)
        
        success_count = sum(1 for r in results if r["success"])
        failure_count = settings.SCAN_RETRIES - success_count
        
        final_status = "success" if success_count > failure_count else "error"
        
        last_result = results[-1]
        
        gateway.status = final_status
        gateway.response_time = last_result.get("response_time")
        gateway.lora_ok = last_result.get("lora_ok", False)
        gateway.total_cards = last_result.get("total_cards", 0)
        gateway.active_cards = last_result.get("active_cards", 0)
        gateway.failed_cards = last_result.get("failed_cards", 0)
        gateway.last_scan = datetime.utcnow()
        
        if final_status == "error" and failure_count == settings.SCAN_RETRIES:
            await alarm_service.create_alarm(
                db,
                plant_id=plant.id,
                alarm_type="gateway_down",
                description=f"Gateway {gateway.ip} no responde despues de {settings.SCAN_RETRIES} intentos",
                gateway_id=gateway.id,
                gateway_ip=gateway.ip
            )
        elif final_status == "success":
            active_alarms = db.query(Alarm).filter(
                Alarm.gateway_id == gateway.id,
                Alarm.alarm_type == "gateway_down",
                Alarm.status == "active"
            ).all()
            for alarm in active_alarms:
                await alarm_service.resolve_alarm(db, alarm.id)
        
        for card_data in last_result.get("cards", []):
            existing_card = db.query(Card).filter(
                Card.gateway_id == gateway.id,
                Card.modbus_id == card_data["modbus_id"]
            ).first()
            
            if existing_card:
                existing_card.communication_ok = card_data.get("communication_ok", False)
                existing_card.last_contact = datetime.utcnow() if card_data.get("active") else existing_card.last_contact
                
                if not card_data.get("active") and not existing_card.maintenance_mode and not existing_card.disabled:
                    if existing_card.status != "error":
                        await alarm_service.create_alarm(
                            db,
                            plant_id=plant.id,
                            alarm_type="card_communication_lost",
                            description=f"Tarjeta {card_data['modbus_id']} sin comunicacion",
                            gateway_id=gateway.id,
                            card_id=existing_card.id,
                            gateway_ip=gateway.ip
                        )
                    existing_card.status = "error"
                else:
                    existing_card.status = "active"
            else:
                new_card = Card(
                    gateway_id=gateway.id,
                    modbus_id=card_data["modbus_id"],
                    status="active" if card_data.get("active") else "error",
                    communication_ok=card_data.get("communication_ok", False),
                    last_contact=datetime.utcnow() if card_data.get("active") else None
                )
                db.add(new_card)
        
        db.commit()
        
        self.cleanup_old_scans(db, gateway.id)
        
        return last_result
    
    def cleanup_old_scans(self, db: Session, gateway_id: int):
        scans = db.query(Scan).filter(Scan.gateway_id == gateway_id).order_by(Scan.created_at.desc()).all()
        
        if len(scans) > 5:
            for scan in scans[5:]:
                db.delete(scan)
            db.commit()
    
    async def scan_plant(self, plant: Plant) -> bool:
        db = SessionLocal()
        try:
            plant_path = plant.path
            vpn_file = f"{plant_path}\\vpn.txt"
            
            if not await vpn_service.connect_vpn(vpn_file, plant.name):
                logger.error(f"No se pudo conectar VPN para planta {plant.name}")
                plant.status = "vpn_error"
                db.commit()
                return False
            
            plant.last_vpn_connection = datetime.utcnow()
            db.commit()
            
            gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
            
            if not gateways:
                ips_file = f"{plant_path}\\ips.txt"
                try:
                    with open(ips_file, 'r') as f:
                        ips = [line.strip() for line in f if line.strip()]
                    
                    for ip in ips:
                        gateway = Gateway(plant_id=plant.id, ip=ip, status="unknown")
                        db.add(gateway)
                    db.commit()
                    gateways = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
                except Exception as e:
                    logger.error(f"Error leyendo IPs para {plant.name}: {e}")
            
            for gateway in gateways:
                await self.scan_gateway_with_retries(db, gateway, plant)
            
            await vpn_service.disconnect_vpn()
            
            plant.status = "scanned"
            plant.last_scan = datetime.utcnow()
            db.commit()
            
            return True
            
        except Exception as e:
            logger.error(f"Error escaneando planta {plant.name}: {e}")
            await vpn_service.disconnect_vpn()
            return False
        finally:
            db.close()
    
    async def scan_all_plants(self):
        if self.scanning:
            logger.warning("Ya hay un escaneo en progreso")
            return
        
        self.scanning = True
        logger.info("Iniciando escaneo de todas las plantas")
        
        try:
            plant_discovery.sync_plants_to_db()
            
            db = SessionLocal()
            plants = db.query(Plant).all()
            db.close()
            
            for plant in plants:
                await self.scan_plant(plant)
                await asyncio.sleep(5)
            
            logger.info("Escaneo completado")
            
        except Exception as e:
            logger.error(f"Error en scan_all_plants: {e}")
        finally:
            self.scanning = False

scan_service = ScanService()
'@ | Out-File -FilePath "app\services\scan_service.py" -Encoding UTF8

# app/api/__init__.py
@'
'@ | Out-File -FilePath "app\api\__init__.py" -Encoding UTF8

# app/api/deps.py
@'
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User

security = HTTPBearer()

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    token = credentials.credentials
    payload = decode_access_token(token)
    
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido"
        )
    
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalido"
        )
    
    user = db.query(User).filter(User.id == int(user_id)).first()
    
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo"
        )
    
    return user

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requieren permisos de administrador"
        )
    return current_user
'@ | Out-File -FilePath "app\api\deps.py" -Encoding UTF8

# app/api/endpoints/__init__.py
@'
'@ | Out-File -FilePath "app\api\endpoints\__init__.py" -Encoding UTF8

# app/api/endpoints/auth.py
@'
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from app.core.database import get_db
from app.core.security import verify_password, create_access_token
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse

router = APIRouter()

@router.post("/login", response_model=TokenResponse)
async def login(request: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == request.username).first()
    
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas"
        )
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Usuario inactivo"
        )
    
    access_token_expires = timedelta(minutes=1440)
    access_token = create_access_token(
        data={"sub": str(user.id)},
        expires_delta=access_token_expires
    )
    
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user_id=user.id,
        username=user.username,
        role=user.role
    )
'@ | Out-File -FilePath "app\api\endpoints\auth.py" -Encoding UTF8

# app/api/endpoints/plants.py
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.alarm import Alarm
from app.schemas.plant import PlantResponse
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[PlantResponse])
async def get_plants(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "admin":
        plants = db.query(Plant).all()
    else:
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        plants = db.query(Plant).filter(Plant.name.in_(assigned)).all()
    
    result = []
    for plant in plants:
        gateways_count = db.query(Gateway).filter(Gateway.plant_id == plant.id).count()
        active_alarms = db.query(Alarm).filter(
            Alarm.plant_id == plant.id,
            Alarm.status == "active"
        ).count()
        
        plant_dict = {
            "id": plant.id,
            "name": plant.name,
            "path": plant.path,
            "status": plant.status,
            "last_scan": plant.last_scan,
            "last_vpn_connection": plant.last_vpn_connection,
            "client_id": plant.client_id,
            "created_at": plant.created_at,
            "updated_at": plant.updated_at,
            "gateways_count": gateways_count,
            "total_cards": 0,
            "active_alarms": active_alarms
        }
        result.append(PlantResponse(**plant_dict))
    
    return result

@router.get("/{plant_id}", response_model=PlantResponse)
async def get_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    
    if current_user.role != "admin":
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        if plant.name not in assigned:
            raise HTTPException(status_code=403, detail="Sin acceso a esta planta")
    
    gateways_count = db.query(Gateway).filter(Gateway.plant_id == plant.id).count()
    active_alarms = db.query(Alarm).filter(
        Alarm.plant_id == plant.id,
        Alarm.status == "active"
    ).count()
    
    return PlantResponse(
        id=plant.id,
        name=plant.name,
        path=plant.path,
        status=plant.status,
        last_scan=plant.last_scan,
        last_vpn_connection=plant.last_vpn_connection,
        client_id=plant.client_id,
        created_at=plant.created_at,
        updated_at=plant.updated_at,
        gateways_count=gateways_count,
        total_cards=0,
        active_alarms=active_alarms
    )
'@ | Out-File -FilePath "app\api\endpoints\plants.py" -Encoding UTF8

# app/api/endpoints/gateways.py
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.gateway import Gateway
from app.models.plant import Plant
from app.schemas.gateway import GatewayResponse
from app.models.user import User

router = APIRouter()

@router.get("/plant/{plant_id}", response_model=List[GatewayResponse])
async def get_gateways_by_plant(
    plant_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plant = db.query(Plant).filter(Plant.id == plant_id).first()
    
    if not plant:
        raise HTTPException(status_code=404, detail="Planta no encontrada")
    
    if current_user.role != "admin":
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        if plant.name not in assigned:
            raise HTTPException(status_code=403, detail="Sin acceso a esta planta")
    
    gateways = db.query(Gateway).filter(Gateway.plant_id == plant_id).all()
    return gateways

@router.get("/{gateway_id}", response_model=GatewayResponse)
async def get_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    return gateway
'@ | Out-File -FilePath "app\api\endpoints\gateways.py" -Encoding UTF8

# app/api/endpoints/cards.py
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.card import Card
from app.models.gateway import Gateway
from app.schemas.card import CardResponse, CardUpdate
from app.models.user import User

router = APIRouter()

@router.get("/gateway/{gateway_id}", response_model=List[CardResponse])
async def get_cards_by_gateway(
    gateway_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    
    cards = db.query(Card).filter(Card.gateway_id == gateway_id).all()
    return cards

@router.patch("/{card_id}", response_model=CardResponse)
async def update_card(
    card_id: int,
    card_update: CardUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    card = db.query(Card).filter(Card.id == card_id).first()
    
    if not card:
        raise HTTPException(status_code=404, detail="Tarjeta no encontrada")
    
    if card_update.maintenance_mode is not None:
        card.maintenance_mode = card_update.maintenance_mode
    
    if card_update.disabled is not None:
        card.disabled = card_update.disabled
    
    db.commit()
    db.refresh(card)
    
    return card
'@ | Out-File -FilePath "app\api\endpoints\cards.py" -Encoding UTF8

# app/api/endpoints/alarms.py
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
from app.core.database import get_db
from app.api.deps import get_current_user
from app.models.alarm import Alarm
from app.schemas.alarm import AlarmResponse
from app.models.user import User

router = APIRouter()

@router.get("/", response_model=List[AlarmResponse])
async def get_alarms(
    status: Optional[str] = None,
    plant_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Alarm)
    
    if status:
        query = query.filter(Alarm.status == status)
    
    if plant_id:
        query = query.filter(Alarm.plant_id == plant_id)
    
    if current_user.role != "admin":
        assigned = current_user.assigned_plants.split(",") if current_user.assigned_plants else []
        from app.models.plant import Plant
        plant_ids = [p.id for p in db.query(Plant).filter(Plant.name.in_(assigned)).all()]
        query = query.filter(Alarm.plant_id.in_(plant_ids))
    
    alarms = query.order_by(Alarm.created_at.desc()).all()
    return alarms

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
'@ | Out-File -FilePath "app\api\endpoints\alarms.py" -Encoding UTF8

# app/api/endpoints/users.py
@'
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.api.deps import require_admin
from app.models.user import User
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.core.security import get_password_hash

router = APIRouter()

@router.get("/", response_model=List[UserResponse])
async def get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    users = db.query(User).all()
    return users

@router.post("/", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    existing_user = db.query(User).filter(
        (User.username == user_data.username) | (User.email == user_data.email)
    ).first()
    
    if existing_user:
        raise HTTPException(status_code=400, detail="Usuario o email ya existe")
    
    user = User(
        username=user_data.username,
        email=user_data.email,
        hashed_password=get_password_hash(user_data.password),
        full_name=user_data.full_name,
        role=user_data.role,
        assigned_plants=user_data.assigned_plants
    )
    
    db.add(user)
    db.commit()
    db.refresh(user)
    
    return user

@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    for field, value in user_update.dict(exclude_unset=True).items():
        setattr(user, field, value)
    
    db.commit()
    db.refresh(user)
    
    return user

@router.delete("/{user_id}")
async def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    user = db.query(User).filter(User.id == user_id).first()
    
    if not user:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")
    
    db.delete(user)
    db.commit()
    
    return {"message": "Usuario eliminado"}
'@ | Out-File -FilePath "app\api\endpoints\users.py" -Encoding UTF8

# app/api/endpoints/websocket.py
@'
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio

router = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@router.websocket("/status")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            await websocket.send_text(f"Message received: {data}")
    except WebSocketDisconnect:
        manager.disconnect(websocket)

async def broadcast_update(update_type: str, data: dict):
    await manager.broadcast({"type": update_type, "data": data})
'@ | Out-File -FilePath "app\api\endpoints\websocket.py" -Encoding UTF8

# app/tasks/__init__.py
@'
'@ | Out-File -FilePath "app\tasks\__init__.py" -Encoding UTF8

# app/tasks/scheduler.py
@'
import asyncio
import logging
from datetime import datetime
from app.services.scan_service import scan_service
from app.services.alarm_service import alarm_service
from app.services.plant_discovery import plant_discovery
from app.core.database import SessionLocal
from app.core.config import settings

logger = logging.getLogger(__name__)

scheduler_running = False

async def start_scheduler():
    global scheduler_running
    scheduler_running = True
    logger.info("Scheduler iniciado")
    
    while scheduler_running:
        try:
            logger.info(f"Iniciando ciclo de escaneo: {datetime.utcnow()}")
            
            plant_discovery.sync_plants_to_db()
            
            await scan_service.scan_all_plants()
            
            db = SessionLocal()
            try:
                reminders = await alarm_service.check_reminders(db)
                if reminders > 0:
                    logger.info(f"Se enviaron {reminders} recordatorios de alarmas")
            finally:
                db.close()
            
            logger.info(f"Ciclo completado. Esperando {settings.SCAN_INTERVAL_SECONDS} segundos")
            await asyncio.sleep(settings.SCAN_INTERVAL_SECONDS)
            
        except Exception as e:
            logger.error(f"Error en el scheduler: {e}")
            await asyncio.sleep(60)

def stop_scheduler():
    global scheduler_running
    scheduler_running = False
    logger.info("Scheduler detenido")
'@ | Out-File -FilePath "app\tasks\scheduler.py" -Encoding UTF8

# requirements.txt
@'
fastapi==0.115.0
uvicorn[standard]==0.32.0
sqlalchemy==2.0.36
pydantic==2.9.2
pydantic-settings==2.6.1
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
pymodbus==3.7.4
python-multipart==0.0.12
email-validator==2.2.0
websockets==13.1
'@ | Out-File -FilePath "requirements.txt" -Encoding UTF8

# .env.example
@'
# Configuracion de la aplicacion
APP_NAME=Webdom Monitor
DATABASE_URL=sqlite:///./webdom_monitor.db
SECRET_KEY=cambia-esta-clave-en-produccion
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# CORS
CORS_ORIGINS=["http://localhost:5173", "http://localhost:3000"]

# Email (Gmail SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=webdomreports@gmail.com
SMTP_PASSWORD=tu-password-de-aplicacion

# Escaneo
SCAN_INTERVAL_SECONDS=300
SCAN_RETRIES=5
ALARM_REMINDER_DAYS=7

# Modbus
MODBUS_PORT=502
MODBUS_TIMEOUT=5.0

# VPN
VPN_EXECUTABLE_OPENVPN=C:\Program Files\OpenVPN\bin\openvpn.exe
VPN_EXECUTABLE_FORTICLIENT=C:\Program Files\Fortinet\FortiClient\FortiClient.exe
'@ | Out-File -FilePath ".env.example" -Encoding UTF8

# run.py
@'
import uvicorn
import sys

if __name__ == "__main__":
    port = 8000
    host = "0.0.0.0"
    
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    
    print(f"Iniciando Webdom Monitor en {host}:{port}")
    print(f"Documentacion API: http://{host}:{port}/docs")
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
'@ | Out-File -FilePath "run.py" -Encoding UTF8

Write-Host "Backend completado!" -ForegroundColor Green

# ============================================
# FRONTEND - Archivos React/TypeScript
# ============================================

Write-Host "Creando archivos del Frontend..." -ForegroundColor Yellow

# package.json
@'
{
  "name": "webdom-monitor-frontend",
  "private": true,
  "version": "1.0.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "tsc && vite build",
    "preview": "vite preview"
  },
  "dependencies": {
    "react": "^18.3.1",
    "react-dom": "^18.3.1",
    "react-router-dom": "^6.28.0",
    "axios": "^1.7.7",
    "lucide-react": "^0.460.0",
    "recharts": "^2.13.3",
    "date-fns": "^4.1.0",
    "clsx": "^2.1.1"
  },
  "devDependencies": {
    "@types/react": "^18.3.12",
    "@types/react-dom": "^18.3.1",
    "@vitejs/plugin-react": "^4.3.3",
    "autoprefixer": "^10.4.20",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.15",
    "typescript": "^5.6.3",
    "vite": "^5.4.11"
  }
}
'@ | Out-File -FilePath "frontend\package.json" -Encoding UTF8

# vite.config.ts
@'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws': {
        target: 'ws://localhost:8000',
        ws: true
      }
    }
  }
})
'@ | Out-File -FilePath "frontend\vite.config.ts" -Encoding UTF8

# tsconfig.json
@'
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true
  },
  "include": ["src"],
  "references": [{ "path": "./tsconfig.node.json" }]
}
'@ | Out-File -FilePath "frontend\tsconfig.json" -Encoding UTF8

# tsconfig.node.json
@'
{
  "compilerOptions": {
    "composite": true,
    "skipLibCheck": true,
    "module": "ESNext",
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true
  },
  "include": ["vite.config.ts"]
}
'@ | Out-File -FilePath "frontend\tsconfig.node.json" -Encoding UTF8

# tailwind.config.js
@'
/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          500: '#0ea5e9',
          600: '#0284c7',
          700: '#0369a1',
          900: '#0c4a6e',
        }
      }
    },
  },
  plugins: [],
}
'@ | Out-File -FilePath "frontend\tailwind.config.js" -Encoding UTF8

# postcss.config.js
@'
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
'@ | Out-File -FilePath "frontend\postcss.config.js" -Encoding UTF8

# index.html
@'
<!doctype html>
<html lang="es">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Webdom Monitor</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
'@ | Out-File -FilePath "frontend\index.html" -Encoding UTF8

# src/main.tsx
@'
import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'
import './index.css'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
'@ | Out-File -FilePath "frontend\src\main.tsx" -Encoding UTF8

# src/index.css
@'
@tailwind base;
@tailwind components;
@tailwind utilities;

:root {
  font-family: Inter, system-ui, Avenir, Helvetica, Arial, sans-serif;
  line-height: 1.5;
  font-weight: 400;
  color-scheme: light dark;
  font-synthesis: none;
  text-rendering: optimizeLegibility;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

body {
  margin: 0;
  min-width: 320px;
  min-height: 100vh;
}

* {
  box-sizing: border-box;
}
'@ | Out-File -FilePath "frontend\src\index.css" -Encoding UTF8

# src/vite-env.d.ts
@'
/// <reference types="vite/client" />
'@ | Out-File -FilePath "frontend\src\vite-env.d.ts" -Encoding UTF8

# src/App.tsx
@'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './context/AuthContext'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import PlantDetail from './pages/PlantDetail'
import Login from './pages/Login'

function PrivateRoute({ children }: { children: React.ReactNode }) {
  const { user } = useAuth()
  return user ? <>{children}</> : <Navigate to="/login" />
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<PrivateRoute><Layout /></PrivateRoute>}>
        <Route index element={<Dashboard />} />
        <Route path="plant/:plantId" element={<PlantDetail />} />
      </Route>
    </Routes>
  )
}

function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}

export default App
'@ | Out-File -FilePath "frontend\src\App.tsx" -Encoding UTF8

# src/types/index.ts
@'
export interface Plant {
  id: number
  name: string
  path: string
  status: string
  last_scan: string | null
  last_vpn_connection: string | null
  client_id: string | null
  created_at: string
  updated_at: string
  gateways_count: number
  total_cards: number
  active_alarms: number
}

export interface Gateway {
  id: number
  plant_id: number
  ip: string
  status: string
  firmware: string | null
  response_time: number | null
  total_cards: number
  active_cards: number
  failed_cards: number
  lora_ok: boolean
  last_scan: string | null
  created_at: string
  updated_at: string
}

export interface Card {
  id: number
  gateway_id: number
  modbus_id: number
  status: string
  communication_ok: boolean
  sec_alarm: boolean
  overvoltage_alarm: boolean
  communication_alarm: boolean
  maintenance_mode: boolean
  disabled: boolean
  last_contact: string | null
  created_at: string
  updated_at: string
}

export interface Alarm {
  id: number
  plant_id: number
  gateway_id: number | null
  card_id: number | null
  gateway_ip: string | null
  alarm_type: string
  description: string | null
  status: string
  created_at: string
  resolved_at: string | null
  active_duration_minutes: number
  observations: string | null
}

export interface User {
  id: number
  username: string
  email: string
  full_name: string | null
  role: string
  assigned_plants: string | null
  is_active: boolean
}

export interface AuthResponse {
  access_token: string
  token_type: string
  user_id: number
  username: string
  role: string
}
'@ | Out-File -FilePath "frontend\src\types\index.ts" -Encoding UTF8

# src/services/api.ts
@'
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json'
  }
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)

export const authAPI = {
  login: (username: string, password: string) =>
    api.post('/auth/login', { username, password })
}

export const plantsAPI = {
  getAll: () => api.get('/plants/'),
  getById: (id: number) => api.get(`/plants/${id}`)
}

export const gatewaysAPI = {
  getByPlant: (plantId: number) => api.get(`/gateways/plant/${plantId}`),
  getById: (id: number) => api.get(`/gateways/${id}`)
}

export const cardsAPI = {
  getByGateway: (gatewayId: number) => api.get(`/cards/gateway/${gatewayId}`),
  update: (id: number, data: any) => api.patch(`/cards/${id}`, data)
}

export const alarmsAPI = {
  getAll: (params?: any) => api.get('/alarms/', { params }),
  getById: (id: number) => api.get(`/alarms/${id}`),
  resolve: (id: number) => api.post(`/alarms/${id}/resolve`)
}

export const usersAPI = {
  getAll: () => api.get('/users/'),
  create: (data: any) => api.post('/users/', data),
  update: (id: number, data: any) => api.patch(`/users/${id}`, data),
  delete: (id: number) => api.delete(`/users/${id}`)
}

export default api
'@ | Out-File -FilePath "frontend\src\services\api.ts" -Encoding UTF8

# src/context/AuthContext.tsx
@'
import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User, AuthResponse } from '../types'

interface AuthContextType {
  user: User | null
  token: string | null
  login: (token: string, user: User) => void
  logout: () => void
  isAuthenticated: boolean
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)

  useEffect(() => {
    const savedToken = localStorage.getItem('access_token')
    const savedUser = localStorage.getItem('user')
    
    if (savedToken && savedUser) {
      setToken(savedToken)
      setUser(JSON.parse(savedUser))
    }
  }, [])

  const login = (newToken: string, newUser: User) => {
    setToken(newToken)
    setUser(newUser)
    localStorage.setItem('access_token', newToken)
    localStorage.setItem('user', JSON.stringify(newUser))
  }

  const logout = () => {
    setToken(null)
    setUser(null)
    localStorage.removeItem('access_token')
    localStorage.removeItem('user')
  }

  return (
    <AuthContext.Provider value={{
      user,
      token,
      login,
      logout,
      isAuthenticated: !!token
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
'@ | Out-File -FilePath "frontend\src\context\AuthContext.tsx" -Encoding UTF8

# src/components/Layout.tsx
@'
import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { LayoutDashboard, LogOut, Moon, Sun } from 'lucide-react'
import { useState } from 'react'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const [darkMode, setDarkMode] = useState(false)

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className={`min-h-screen ${darkMode ? 'bg-gray-900' : 'bg-gray-50'}`}>
      <nav className={`${darkMode ? 'bg-gray-800 border-gray-700' : 'bg-white border-gray-200'} border-b shadow-sm`}>
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            <div className="flex items-center">
              <Link to="/" className="flex items-center space-x-2">
                <LayoutDashboard className="h-8 w-8 text-blue-600" />
                <span className={`text-xl font-bold ${darkMode ? 'text-white' : 'text-gray-900'}`}>
                  Webdom Monitor
                </span>
              </Link>
            </div>
            
            <div className="flex items-center space-x-4">
              <button
                onClick={() => setDarkMode(!darkMode)}
                className={`p-2 rounded-lg ${darkMode ? 'bg-gray-700 text-yellow-400' : 'bg-gray-100 text-gray-600'}`}
              >
                {darkMode ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
              </button>
              
              <div className={`text-sm ${darkMode ? 'text-gray-300' : 'text-gray-700'}`}>
                {user?.username} ({user?.role})
              </div>
              
              <button
                onClick={handleLogout}
                className="flex items-center space-x-1 px-3 py-2 text-sm text-red-600 hover:bg-red-50 rounded-lg"
              >
                <LogOut className="h-4 w-4" />
                <span>Salir</span>
              </button>
            </div>
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 px-4 sm:px-6 lg:px-8">
        <Outlet />
      </main>
    </div>
  )
}
'@ | Out-File -FilePath "frontend\src\components\Layout.tsx" -Encoding UTF8

# src/pages/Login.tsx
@'
import { useState, FormEvent } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext'
import { authAPI } from '../services/api'
import { LayoutDashboard } from 'lucide-react'

export default function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()
  const { login } = useAuth()

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const response = await authAPI.login(username, password)
      const { access_token, user_id, username: uname, role } = response.data
      
      login(access_token, {
        id: user_id,
        username: uname,
        email: '',
        full_name: null,
        role: role,
        assigned_plants: null,
        is_active: true
      })
      
      navigate('/')
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Error al iniciar sesion')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-blue-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="max-w-md w-full bg-white rounded-2xl shadow-xl p-8">
        <div className="flex flex-col items-center mb-8">
          <div className="bg-blue-600 p-3 rounded-full mb-4">
            <LayoutDashboard className="h-8 w-8 text-white" />
          </div>
          <h1 className="text-3xl font-bold text-gray-900">Webdom Monitor</h1>
          <p className="text-gray-600 mt-2">Plataforma de Monitorizacion</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded-lg">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="username" className="block text-sm font-medium text-gray-700 mb-2">
              Usuario
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-gray-700 mb-2">
              Contraseña
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              required
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-blue-600 text-white py-3 px-4 rounded-lg font-medium hover:bg-blue-700 focus:ring-4 focus:ring-blue-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? 'Iniciando sesion...' : 'Iniciar Sesion'}
          </button>
        </form>
      </div>
    </div>
  )
}
'@ | Out-File -FilePath "frontend\src\pages\Login.tsx" -Encoding UTF8

# src/pages/Dashboard.tsx
@'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { plantsAPI } from '../services/api'
import { Plant } from '../types'
import { Activity, AlertTriangle, CheckCircle, Wifi, Zap } from 'lucide-react'

export default function Dashboard() {
  const [plants, setPlants] = useState<Plant[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadPlants()
    const interval = setInterval(loadPlants, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadPlants = async () => {
    try {
      const response = await plantsAPI.getAll()
      setPlants(response.data)
    } catch (error) {
      console.error('Error cargando plantas:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'scanned': return 'bg-green-100 text-green-800 border-green-200'
      case 'vpn_error': return 'bg-red-100 text-red-800 border-red-200'
      case 'unknown': return 'bg-gray-100 text-gray-800 border-gray-200'
      default: return 'bg-yellow-100 text-yellow-800 border-yellow-200'
    }
  }

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'scanned': return <CheckCircle className="h-5 w-5 text-green-600" />
      case 'vpn_error': return <AlertTriangle className="h-5 w-5 text-red-600" />
      default: return <Activity className="h-5 w-5 text-gray-600" />
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Cargando plantas...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900">Dashboard</h1>
        <button
          onClick={loadPlants}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          Actualizar
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {plants.map((plant) => (
          <Link
            key={plant.id}
            to={`/plant/${plant.id}`}
            className="bg-white rounded-xl shadow-md hover:shadow-lg transition-shadow border border-gray-200 p-6"
          >
            <div className="flex items-start justify-between mb-4">
              <div>
                <h3 className="text-xl font-semibold text-gray-900">{plant.name}</h3>
                <p className="text-sm text-gray-500 mt-1">
                  Ultima actualizacion: {plant.last_scan ? new Date(plant.last_scan).toLocaleString('es-ES') : 'Nunca'}
                </p>
              </div>
              <div className={`px-3 py-1 rounded-full border ${getStatusColor(plant.status)} flex items-center space-x-1`}>
                {getStatusIcon(plant.status)}
                <span className="text-xs font-medium capitalize">{plant.status}</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4 mt-4">
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <Wifi className="h-5 w-5 text-blue-600" />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.gateways_count}</div>
                <div className="text-xs text-gray-500">Gateways</div>
              </div>
              
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <Zap className="h-5 w-5 text-green-600" />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.total_cards}</div>
                <div className="text-xs text-gray-500">Tarjetas</div>
              </div>
              
              <div className="text-center">
                <div className="flex items-center justify-center mb-1">
                  <AlertTriangle className={`h-5 w-5 ${plant.active_alarms > 0 ? 'text-red-600' : 'text-gray-400'}`} />
                </div>
                <div className="text-2xl font-bold text-gray-900">{plant.active_alarms}</div>
                <div className="text-xs text-gray-500">Alarmas</div>
              </div>
            </div>
          </Link>
        ))}
      </div>

      {plants.length === 0 && (
        <div className="text-center py-12 bg-white rounded-xl shadow-md">
          <Activity className="h-16 w-16 text-gray-400 mx-auto mb-4" />
          <h3 className="text-xl font-medium text-gray-900 mb-2">No hay plantas configuradas</h3>
          <p className="text-gray-600">
            Crea carpetas en el directorio plants/ para comenzar a monitorizar
          </p>
        </div>
      )}
    </div>
  )
}
'@ | Out-File -FilePath "frontend\src\pages\Dashboard.tsx" -Encoding UTF8

# src/pages/PlantDetail.tsx
@'
import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { plantsAPI, gatewaysAPI, alarmsAPI } from '../services/api'
import { Plant, Gateway, Alarm } from '../types'
import { ArrowLeft, Wifi, Activity, AlertTriangle, CheckCircle, Clock } from 'lucide-react'

export default function PlantDetail() {
  const { plantId } = useParams<{ plantId: string }>()
  const [plant, setPlant] = useState<Plant | null>(null)
  const [gateways, setGateways] = useState<Gateway[]>([])
  const [alarms, setAlarms] = useState<Alarm[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (plantId) {
      loadData()
    }
  }, [plantId])

  const loadData = async () => {
    try {
      const [plantRes, gatewaysRes, alarmsRes] = await Promise.all([
        plantsAPI.getById(parseInt(plantId!)),
        gatewaysAPI.getByPlant(parseInt(plantId!)),
        alarmsAPI.getAll({ plant_id: plantId })
      ])
      
      setPlant(plantRes.data)
      setGateways(gatewaysRes.data)
      setAlarms(alarmsRes.data)
    } catch (error) {
      console.error('Error cargando datos:', error)
    } finally {
      setLoading(false)
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'success': return 'bg-green-100 text-green-800'
      case 'error': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    )
  }

  if (!plant) {
    return <div className="text-center py-12">Planta no encontrada</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center space-x-4">
        <Link
          to="/"
          className="p-2 hover:bg-gray-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="h-6 w-6" />
        </Link>
        <div>
          <h1 className="text-3xl font-bold text-gray-900">{plant.name}</h1>
          <p className="text-gray-600 mt-1">
            Ultima actualizacion: {plant.last_scan ? new Date(plant.last_scan).toLocaleString('es-ES') : 'Nunca'}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <Wifi className="h-8 w-8 text-blue-600" />
            <span className="text-3xl font-bold text-gray-900">{gateways.length}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Gateways</h3>
        </div>

        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <Activity className="h-8 w-8 text-green-600" />
            <span className="text-3xl font-bold text-gray-900">{plant.total_cards}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Tarjetas</h3>
        </div>

        <div className="bg-white rounded-xl shadow-md p-6">
          <div className="flex items-center justify-between mb-2">
            <AlertTriangle className="h-8 w-8 text-red-600" />
            <span className="text-3xl font-bold text-gray-900">{plant.active_alarms}</span>
          </div>
          <h3 className="text-sm font-medium text-gray-600">Alarmas Activas</h3>
        </div>
      </div>

      <div className="bg-white rounded-xl shadow-md">
        <div className="px-6 py-4 border-b border-gray-200">
          <h2 className="text-xl font-semibold text-gray-900">Gateways</h2>
        </div>
        <div className="divide-y divide-gray-200">
          {gateways.map((gateway) => (
            <div key={gateway.id} className="px-6 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-3">
                  <div className={`p-2 rounded-lg ${getStatusColor(gateway.status)}`}>
                    {gateway.status === 'success' ? (
                      <CheckCircle className="h-5 w-5 text-green-600" />
                    ) : (
                      <AlertTriangle className="h-5 w-5 text-red-600" />
                    )}
                  </div>
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{gateway.ip}</h3>
                    <p className="text-sm text-gray-500">
                      Firmware: {gateway.firmware || 'N/A'} |
                      Respuesta: {gateway.response_time ? `${gateway.response_time.toFixed(2)}s` : 'N/A'}
                    </p>
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm text-gray-600">
                    <span className="font-medium">{gateway.active_cards}</span> / {gateway.total_cards} tarjetas
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    LoRa: {gateway.lora_ok ? '✓ OK' : '✗ Error'}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {alarms.length > 0 && (
        <div className="bg-white rounded-xl shadow-md">
          <div className="px-6 py-4 border-b border-gray-200">
            <h2 className="text-xl font-semibold text-gray-900">Alarmas</h2>
          </div>
          <div className="divide-y divide-gray-200">
            {alarms.slice(0, 10).map((alarm) => (
              <div key={alarm.id} className="px-6 py-4">
                <div className="flex items-start justify-between">
                  <div>
                    <h3 className="text-lg font-medium text-gray-900">{alarm.alarm_type}</h3>
                    <p className="text-sm text-gray-600 mt-1">{alarm.description}</p>
                    {alarm.gateway_ip && (
                      <p className="text-xs text-gray-500 mt-1">Gateway: {alarm.gateway_ip}</p>
                    )}
                  </div>
                  <div className="text-right">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      alarm.status === 'active' ? 'bg-red-100 text-red-800' : 'bg-green-100 text-green-800'
                    }`}>
                      {alarm.status}
                    </span>
                    <div className="flex items-center text-xs text-gray-500 mt-2">
                      <Clock className="h-3 w-3 mr-1" />
                      {new Date(alarm.created_at).toLocaleString('es-ES')}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
'@ | Out-File -FilePath "frontend\src\pages\PlantDetail.tsx" -Encoding UTF8

Write-Host "Frontend completado!" -ForegroundColor Green

# ============================================
# Crear usuario administrador inicial
# ============================================

Write-Host "Creando usuario administrador..." -ForegroundColor Yellow

@'
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import SessionLocal, init_db
from app.models.user import User
from app.core.security import get_password_hash
import asyncio

async def create_admin():
    await init_db()
    db = SessionLocal()
    
    existing = db.query(User).filter(User.username == "admin").first()
    if existing:
        print("Usuario admin ya existe")
        db.close()
        return
    
    admin = User(
        username="admin",
        email="admin@webdom.es",
        hashed_password=get_password_hash("admin123"),
        full_name="Administrador",
        role="admin",
        is_active=True
    )
    
    db.add(admin)
    db.commit()
    db.close()
    
    print("Usuario administrador creado:")
    print("  Usuario: admin")
    print("  Contraseña: admin123")
    print("IMPORTANTE: Cambia la contraseña despues del primer login")

if __name__ == "__main__":
    asyncio.run(create_admin())
'@ | Out-File -FilePath "scripts\create_admin.py" -Encoding UTF8

Write-Host ""
Write-Host "=== Proyecto generado exitosamente ===" -ForegroundColor Green
Write-Host ""
Write-Host "Pasos para iniciar:" -ForegroundColor Yellow
Write-Host "1. cd C:\SCADA_MOHAMED\frontend"
Write-Host "2. npm install"
Write-Host "3. npm run dev"
Write-Host ""
Write-Host "4. En otra terminal: cd C:\SCADA_MOHAMED"
Write-Host "5. python scripts\create_admin.py"
Write-Host "6. python run.py"
Write-Host ""
Write-Host "Acceder a: http://localhost:5173" -ForegroundColor Cyan
Write-Host "Usuario: admin | Contraseña: admin123" -ForegroundColor Cyan