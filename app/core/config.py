from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
    # Sondas Modbus simultáneas en todo el proceso (todas las plantas/gateways).
    MODBUS_MAX_WORKERS: int = 128
    # Sondas simultáneas dentro de un mismo gateway: con 32 IDs el barrido
    # completo cabe en una sola tanda (~1 timeout, no 2-3 en serie).
    MODBUS_GATEWAY_CONCURRENCY: int = 32
    # Timeout por lectura Modbus durante el escaneo.
    MODBUS_PROBE_TIMEOUT: float = 1.5
    # Presupuesto máximo del escaneo de un gateway: pasado ese tiempo se
    # devuelve lo que se haya conseguido en vez de dejar la UI colgada.
    SCAN_GATEWAY_BUDGET_SECONDS: float = 10.0

    VPN_EXECUTABLE_OPENVPN: str = "C:\\Program Files\\OpenVPN\\bin\\openvpn.exe"
    VPN_EXECUTABLE_FORTICLIENT: str = "C:\\Program Files\\Fortinet\\FortiClient\\FortiClient.exe"

    VPN_CONNECT_TIMEOUT: float = 45.0
    VPN_VERIFY_TIMEOUT: float = 20.0
    VPN_CONNECT_RETRIES: int = 3
    VPN_AUTO_RECONNECT: bool = True
    VPN_HEALTH_INTERVAL_SECONDS: int = 60
    # Ventana en la que una comprobación de túnel correcta se da por válida sin
    # volver a sondear (evita latencia en operaciones encadenadas).
    VPN_REUSE_GRACE_SECONDS: float = 20.0
    # Tras un fallo de conexión, las peticiones automáticas de esa planta se
    # rechazan al instante durante este tiempo (las manuales lo saltan).
    VPN_FAILURE_COOLDOWN_SECONDS: float = 30.0

    DEMO_MODE: bool = False

settings = Settings()
