"""
Escritura y lectura del `vpn.txt` de una planta.

Centraliza el formato del fichero para que el alta de planta y la edición
posterior desde la web generen exactamente la misma configuración que espera
`vpn_service_v2`.
"""
import base64
import os
from typing import Dict, Optional

from app.schemas.plant import VPNConfigSchema

SECRET_KEYS = {'PASSWORD', 'KEY_PASSWORD', 'PSK', 'PRIVATE_KEY', 'SSH_PASSWORD'}
MASK = '********'
ALLOWED_CONFIG_SUFFIXES = ('.ovpn', '.conf')
MAX_CONFIG_BYTES = 2 * 1024 * 1024


class VPNConfigError(ValueError):
    """Configuración VPN inválida enviada desde la web."""


def _add(lines, key: str, value):
    if value not in (None, ''):
        lines.append(f"{key}={value}")


def build_vpn_lines(vpn: VPNConfigSchema, config_name: Optional[str] = None):
    lines = [f"VPN_TYPE={vpn.type}"]

    if vpn.type == 'openvpn':
        _add(lines, 'CONFIG', config_name or vpn.config_path or 'openvpn.ovpn')
        _add(lines, 'USER', vpn.username)
        _add(lines, 'PASSWORD', vpn.password)
        _add(lines, 'KEY_PASSWORD', vpn.key_password)

    elif vpn.type == 'forticlient':
        _add(lines, 'SUBTYPE', vpn.subtype)
        _add(lines, 'VPN_NAME', vpn.vpn_name)
        _add(lines, 'HOST', vpn.host)
        _add(lines, 'PORT', vpn.port)
        _add(lines, 'USER', vpn.username)
        _add(lines, 'PASSWORD', vpn.password)
        if vpn.subtype == 'ssl':
            _add(lines, 'REALM', vpn.realm)
            _add(lines, 'TRUSTED_CERT', vpn.trusted_cert)
            _add(lines, 'ALLOW_INSECURE', 'true' if vpn.allow_insecure else 'false')
        elif vpn.subtype == 'ipsec':
            _add(lines, 'PSK', vpn.psk)
            _add(lines, 'PRIVATE_KEY', vpn.private_key)
            _add(lines, 'LOCAL_ID', vpn.local_id)
            _add(lines, 'REMOTE_ID', vpn.remote_id)
            _add(lines, 'IKE_VERSION', vpn.ike_version)
            _add(lines, 'PHASE1_PROPOSAL', vpn.phase1_proposal)
            _add(lines, 'PHASE1_DH_GROUP', vpn.phase1_dh_group)
            _add(lines, 'PHASE2_PROPOSAL', vpn.phase2_proposal)
            _add(lines, 'PHASE2_DH_GROUP', vpn.phase2_dh_group)

    elif vpn.type == 'ssh':
        _add(lines, 'SSH_HOST', vpn.ssh_host)
        _add(lines, 'SSH_PORT', vpn.ssh_port)
        _add(lines, 'SSH_USER', vpn.ssh_username)
        _add(lines, 'SSH_PASSWORD', vpn.ssh_password)
        _add(lines, 'SSH_KEY_PATH', vpn.ssh_key_path)

    return lines


def write_plant_vpn(plant_dir: str, vpn: VPNConfigSchema) -> str:
    """Escribe `plant_dir/vpn.txt` (y el .ovpn subido, si lo hay).

    Devuelve la ruta del vpn.txt escrito.
    """
    os.makedirs(plant_dir, exist_ok=True)

    config_name = None
    if vpn.type == 'openvpn' and vpn.config_file:
        config_name = os.path.basename(
            (vpn.config_filename or 'openvpn.ovpn').replace('\\', '/')
        )
        if not config_name or config_name in ('.', '..'):
            raise VPNConfigError("Nombre de archivo .ovpn no válido")
        if not config_name.lower().endswith(ALLOWED_CONFIG_SUFFIXES):
            raise VPNConfigError("El archivo de configuración debe ser .ovpn o .conf")
        try:
            content = base64.b64decode(vpn.config_file, validate=True)
        except (ValueError, TypeError):
            raise VPNConfigError("El contenido del archivo .ovpn no es base64 válido")
        if not content:
            raise VPNConfigError("El archivo .ovpn está vacío")
        if len(content) > MAX_CONFIG_BYTES:
            raise VPNConfigError("El archivo .ovpn supera el tamaño máximo permitido")
        with open(os.path.join(plant_dir, config_name), 'wb') as fh:
            fh.write(content)

    vpn_file = os.path.join(plant_dir, 'vpn.txt')
    existing = read_plant_vpn_raw(vpn_file)

    lines = []
    for line in build_vpn_lines(vpn, config_name):
        key, value = line.split('=', 1)
        # Un secreto que llega enmascarado significa "déjalo como estaba".
        if key in SECRET_KEYS and value == MASK and key in existing:
            line = f"{key}={existing[key]}"
        lines.append(line)

    with open(vpn_file, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(lines) + "\n")
    try:
        os.chmod(vpn_file, 0o600)
    except OSError:
        pass
    return vpn_file


def read_plant_vpn_raw(vpn_file: str) -> Dict[str, str]:
    values: Dict[str, str] = {}
    if not os.path.isfile(vpn_file):
        return values
    with open(vpn_file, 'r', encoding='utf-8', errors='ignore') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip().upper()] = value.strip()
    return values


def read_plant_vpn_masked(vpn_file: str) -> Dict[str, str]:
    """Configuración de la planta con los secretos sustituidos por `MASK`."""
    return {
        key: (MASK if key in SECRET_KEYS and value else value)
        for key, value in read_plant_vpn_raw(vpn_file).items()
    }
