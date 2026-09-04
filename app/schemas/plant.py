from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class PlantBase(BaseModel):
    name: str
    path: str
    client_id: Optional[str] = None

class GatewayCreateSchema(BaseModel):
    ip: str
    id_start: int = 1
    id_end: int = 32

class VPNConfigSchema(BaseModel):
    type: str = "openvpn"  # openvpn, forticlient, ssh
    # OpenVPN
    config_path: Optional[str] = None
    # Fichero .ovpn subido desde la web (base64); se guarda en la carpeta de la
    # planta y pasa a ser el CONFIG del vpn.txt.
    config_file: Optional[str] = None
    config_filename: Optional[str] = None
    # OpenVPN + FortiClient
    username: Optional[str] = None
    password: Optional[str] = None
    key_password: Optional[str] = None
    # FortiClient (subtype: ssl / ipsec)
    subtype: str = "ssl"
    vpn_name: Optional[str] = None
    host: Optional[str] = None
    port: int = 10443
    realm: Optional[str] = None
    trusted_cert: Optional[str] = None
    allow_insecure: bool = True
    psk: Optional[str] = None
    private_key: Optional[str] = None
    local_id: Optional[str] = None
    remote_id: Optional[str] = None
    ike_version: str = "v2"
    # IPsec Advanced: Phase 1
    phase1_proposal: str = "AES256-SHA512"
    phase1_dh_group: str = "14"
    # IPsec Advanced: Phase 2
    phase2_proposal: str = "AES256-SHA512"
    phase2_dh_group: str = "14"
    # SSH
    ssh_host: Optional[str] = None
    ssh_port: int = 22
    ssh_username: Optional[str] = None
    ssh_password: Optional[str] = None
    ssh_key_path: Optional[str] = None

class PlantCreate(BaseModel):
    name: str
    client_id: Optional[str] = None
    gateways: List[GatewayCreateSchema] = []
    vpn: Optional[VPNConfigSchema] = None

class PlantUpdate(BaseModel):
    name: Optional[str] = None
    client_id: Optional[str] = None

class PlantResponse(PlantBase):
    id: int
    status: str
    vpn_status: str = "disconnected"
    response_time_ms: Optional[float] = None
    maintenance_mode: bool = False
    last_scan: Optional[datetime] = None
    last_vpn_connection: Optional[datetime] = None
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