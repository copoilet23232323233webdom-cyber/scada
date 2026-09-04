"""
Contexto de operación sobre un gateway: conecta la VPN de la planta y ejecuta
operaciones Modbus síncronas sobre un cliente persistente.

Tanto el túnel VPN como el socket Modbus se reutilizan entre peticiones (una
operación a la vez por gateway), de modo que sólo la primera operación paga el
coste de conexión.
"""
import asyncio
import logging
import time
from typing import Dict

from app.core.database import SessionLocal
from app.models.gateway import Gateway
from app.services.vpn_service_v2 import resolve_plant_vpn_file, vpn_service
from app.services.modbus_service_v2 import modbus_service
from app.services.gw_control.protocol import ModbusTcpClient
from app.core.config import settings

logger = logging.getLogger(__name__)


def _gateway_routes(gateway: Gateway):
    routes = set()
    if gateway.ip:
        parts = gateway.ip.split('.')
        if len(parts) == 4:
            routes.add(f"{parts[0]}.{parts[1]}.{parts[2]}.0/24")
    return sorted(routes) if routes else None


async def _connect_plant_vpn(gateway: Gateway) -> bool:
    """Conecta la VPN de la planta del gateway. Devuelve True si ok."""
    plant = gateway.plant
    if plant is None:
        logger.error("Gateway sin planta asignada")
        return False
    vpn_file = resolve_plant_vpn_file(plant.path, plant.name)
    if not vpn_file:
        # Planta de acceso directo (LAN): no hay túnel que levantar.
        logger.warning(f"{plant.name}: sin vpn.txt, acceso directo al gateway")
        modbus_service.set_ssh_transport(None)
        return True

    routes = _gateway_routes(gateway)
    # Reutilizar si ya hay una conexión a esta planta (respuesta instantánea)
    if not await vpn_service.connect_vpn(vpn_file, plant.name, routes, [gateway.ip]):
        logger.error(f"VPN falló para {plant.name}")
        return False

    if hasattr(vpn_service, 'ssh_transport') and vpn_service.ssh_transport:
        modbus_service.set_ssh_transport(vpn_service.ssh_transport)
    else:
        modbus_service.set_ssh_transport(None)

    # connect_vpn ya verificó que el gateway responde por el túnel, así que no
    # hace falta esperar a que se estabilicen las rutas.
    return True


# Clientes Modbus vivos por gateway, con su cerrojo para serializar el socket.
_clients: Dict[int, ModbusTcpClient] = {}
_locks: Dict[int, asyncio.Lock] = {}
_last_used: Dict[int, float] = {}

# Un socket parado más de este tiempo se descarta: es más rápido reconectar que
# descubrir en mitad de una lectura que el otro extremo lo cerró.
IDLE_TIMEOUT = 120.0


def _client_for(gateway: Gateway) -> ModbusTcpClient:
    client = _clients.get(gateway.id)
    stale = time.monotonic() - _last_used.get(gateway.id, 0) > IDLE_TIMEOUT
    if client is not None and (client.ip != gateway.ip or stale):
        client.close()
        client = None
    if client is None:
        client = ModbusTcpClient(ip=gateway.ip, port=int(settings.MODBUS_PORT))
        _clients[gateway.id] = client
    _last_used[gateway.id] = time.monotonic()
    return client


def drop_client(gateway_id: int):
    """Cierra el socket persistente de un gateway (tras reset o fallo)."""
    client = _clients.pop(gateway_id, None)
    _last_used.pop(gateway_id, None)
    if client is not None:
        client.close()


def close_all_clients():
    for gateway_id in list(_clients):
        drop_client(gateway_id)


async def run_gateway_op(gateway_id: int, op, *args, **kwargs):
    """
    Ejecuta una operación síncrona 'op(client, *args, **kwargs)' sobre el gateway.
    Gestiona conexión VPN (persistente: se reutiliza la VPN ya conectada para la
    misma planta -> respuestas instantaneas en operaciones repetidas) y cliente Modbus.
    Devuelve el resultado de la operación o un dict de error si no se pudo conectar.
    """
    db = SessionLocal()
    try:
        gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
        if gateway is None:
            return {"ok": False, "error": "Gateway no encontrado"}

        # Reutiliza la VPN si ya estaba conectada a esta planta (sin reconexion)
        if not await _connect_plant_vpn(gateway):
            plant_name = gateway.plant.name if gateway.plant else ""
            retry_in = round(vpn_service.cooldown_remaining(plant_name))
            error = vpn_service.last_error or "No se pudo conectar la VPN de la planta"
            if retry_in:
                error = f"{error} (reintento automático en {retry_in}s)"
            return {
                "ok": False,
                "error": error,
                "retry_in_seconds": retry_in,
                "demo": vpn_service.demo_mode,
            }

        lock = _locks.setdefault(gateway_id, asyncio.Lock())
        async with lock:
            client = _client_for(gateway)
            try:
                return await asyncio.to_thread(op, client, *args, **kwargs)
            except Exception:
                drop_client(gateway_id)
                raise

    except Exception as e:
        logger.error(f"Error en operación gateway {gateway_id}: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()
