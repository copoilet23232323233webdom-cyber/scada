"""
Endpoints de control avanzado de gateways (replican las funciones del programa
multi_gw_control / C#). Cada endpoint conecta la VPN de la planta del gateway,
ejecuta la operación Modbus y desconecta la VPN al finalizar.
"""
import base64
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.core.database import get_db
from app.api.deps import get_current_user, require_admin
from app.models.user import User
from app.models.gateway import Gateway
from app.models.plant import Plant
from app.services.gw_control import operations as ops
from app.services.gw_control import constants as A
from app.services.gw_control import codecs
from app.services.gw_control.context import run_gateway_op

logger = logging.getLogger(__name__)

router = APIRouter()


# =====================================================================
# Esquemas de entrada
# =====================================================================

class LoraConfIn(BaseModel):
    raw_bits: Optional[int] = None
    pream_length: Optional[int] = None
    fixed_pk_length: Optional[int] = None
    frq: Optional[int] = None


class LoraConfWriteIn(BaseModel):
    low_data_rate_opt: Optional[bool] = None
    crc_dis: Optional[bool] = None
    explicit_en: Optional[bool] = None
    fix_pkln_en: Optional[bool] = None
    bandwidth: Optional[int] = None
    coding_rate: Optional[int] = None
    sfactor: Optional[int] = None
    tx_pwr: Optional[int] = None
    pream_length: Optional[int] = None
    fixed_pk_length: Optional[int] = None
    frq: Optional[int] = None


class AnalogChannelIn(BaseModel):
    k: Optional[float] = None
    offset: Optional[float] = None
    n_mean: Optional[float] = None


class ChannelMapIn(BaseModel):
    channels: List[int]  # 32 canales (channel asignado al toroide i)


class SlaveCmdIn(BaseModel):
    cmd: int
    typ: int = 3
    save_nvm: bool = True


class SlaveSelectIn(BaseModel):
    ids: Optional[List[int]] = None  # ids de la tabla CB; si None, todos


class FileContentIn(BaseModel):
    data: str  # base64


class ModeIn(BaseModel):
    mode: int  # 0=DataLog, 1=Config


class CommandIn(BaseModel):
    value: int


# =====================================================================
# Helpers
# =====================================================================

def _require_admin(user: User):
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores")


def _get_gateway(db: Session, gateway_id: int) -> Gateway:
    gateway = db.query(Gateway).filter(Gateway.id == gateway_id).first()
    if not gateway:
        raise HTTPException(status_code=404, detail="Gateway no encontrado")
    return gateway


# =====================================================================
# Operaciones de nivel gateway (estado, config, comandos)
# =====================================================================

@router.get("/{gateway_id}/status")
async def gateway_status(gateway_id: int, db: Session = Depends(get_db),
                         current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.read_gw_status)
    if isinstance(result, dict) and result.get("ok") is False:
        raise HTTPException(status_code=502, detail=result.get("error", "Error de conexión"))
    return result


@router.get("/{gateway_id}/firmware")
async def gateway_firmware(gateway_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.read_version)
    return {"version": result}


@router.get("/{gateway_id}/sys-config")
async def gateway_sys_config(gateway_id: int, db: Session = Depends(get_db),
                             current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.read_sys_config)
    if isinstance(result, dict) and result.get("ok") is False:
        raise HTTPException(status_code=502, detail=result.get("error"))
    return result


@router.post("/{gateway_id}/mode")
async def gateway_set_mode(gateway_id: int, data: ModeIn,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.set_mode, data.mode)
    return {"ok": result is None, "error": result}


@router.post("/{gateway_id}/save-nvm")
async def gateway_save_nvm(gateway_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.save_gw_nvm)
    return {"ok": result is None, "error": result}


@router.post("/{gateway_id}/reset")
async def gateway_reset(gateway_id: int, db: Session = Depends(get_db),
                        current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.reset_gw)
    return {"ok": result is None, "error": result}


@router.post("/{gateway_id}/command")
async def gateway_command(gateway_id: int, data: CommandIn,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.send_gw_command, data.value)
    return {"ok": result is None, "error": result}


# =====================================================================
# Tabla CB
# =====================================================================

@router.get("/{gateway_id}/cb-table")
async def gateway_cb_table(gateway_id: int, db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    result = await run_gateway_op(gateway_id, ops.get_cb_table)
    if not result[0]:
        raise HTTPException(status_code=502, detail=result[1].get("error"))
    data = result[1]
    return {"ok": True, "nslv": data.get("nslv", 0), "items": data.get("items", [])}


# =====================================================================
# Operaciones sobre esclavos
# =====================================================================

@router.get("/{gateway_id}/slaves/{cb_id}/lora")
async def slave_lora_conf(gateway_id: int, cb_id: int,
                          db: Session = Depends(get_db),
                          current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        cb = {"id": cb_id}
        res = ops.read_slave_lora_conf(client, cb)
        return res

    result = await run_gateway_op(gateway_id, _wrap)
    return result


@router.get("/{gateway_id}/slaves/{cb_id}/analog-bottom")
async def slave_analog_bottom(gateway_id: int, cb_id: int,
                              db: Session = Depends(get_db),
                              current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.read_slave_analog_bottom(client, {"id": cb_id})

    return await run_gateway_op(gateway_id, _wrap)


@router.get("/{gateway_id}/slaves/{cb_id}/analog-top")
async def slave_analog_top(gateway_id: int, cb_id: int,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.read_slave_analog_top(client, {"id": cb_id})

    return await run_gateway_op(gateway_id, _wrap)


@router.get("/{gateway_id}/slaves/{cb_id}/channel-map")
async def slave_channel_map(gateway_id: int, cb_id: int,
                            db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.read_slave_channel_map(client, {"id": cb_id})

    return await run_gateway_op(gateway_id, _wrap)


# --- Escrituras ---

@router.post("/{gateway_id}/slaves/{cb_id}/lora")
async def write_slave_lora(gateway_id: int, cb_id: int, data: LoraConfWriteIn,
                           db: Session = Depends(get_db),
                           current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    # construir lora conf a partir de los flags/valores
    lora = _build_lora_from_flags(data)

    def _wrap(client):
        cb = {"id": cb_id}
        return ops.write_slave_lora_conf(client, cb, lora, save_nvm=True)

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/slaves/{cb_id}/analog-bottom")
async def write_slave_analog_bottom(gateway_id: int, cb_id: int, channels: List[AnalogChannelIn],
                                    db: Session = Depends(get_db),
                                    current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    chans = [c.dict() for c in channels]

    def _wrap(client):
        return ops.write_slave_analog_bottom(client, {"id": cb_id}, chans, save_nvm=True)

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/slaves/{cb_id}/analog-top")
async def write_slave_analog_top(gateway_id: int, cb_id: int, channels: List[AnalogChannelIn],
                                 db: Session = Depends(get_db),
                                 current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    chans = [c.dict() for c in channels]

    def _wrap(client):
        return ops.write_slave_analog_top(client, {"id": cb_id}, chans, save_nvm=True)

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/slaves/{cb_id}/channel-map")
async def write_slave_channel_map(gateway_id: int, cb_id: int, data: ChannelMapIn,
                                  db: Session = Depends(get_db),
                                  current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.write_slave_channel_map(client, {"id": cb_id}, data.channels, save_nvm=True)

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/slaves/{cb_id}/command")
async def send_slave_cmd(gateway_id: int, cb_id: int, data: SlaveCmdIn,
                         db: Session = Depends(get_db),
                         current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.send_ssx_cmd(client, {"id": cb_id}, data.cmd, data.typ, data.save_nvm)

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/slaves/{cb_id}/zero")
async def slave_zero(gateway_id: int, cb_id: int, data: Optional[dict] = None,
                     db: Session = Depends(get_db),
                     current_user: User = Depends(require_admin)):
    typ = (data or {}).get("typ", 3)
    _get_gateway(db, gateway_id)

    def _wrap(client):
        return ops.send_ssx_cmd(client, {"id": cb_id}, A.CMD_ZERO, typ, True)

    return await run_gateway_op(gateway_id, _wrap)


# =====================================================================
# Escaneo LoRa
# =====================================================================

@router.post("/{gateway_id}/lora-scan")
async def gateway_lora_scan(gateway_id: int, data: Optional[SlaveSelectIn] = None,
                            db: Session = Depends(get_db),
                            current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    selected_ids = set((data or {}).ids or []) if isinstance(data, SlaveSelectIn) or data else set()

    def _wrap(client):
        res = ops.get_cb_table(client)
        if not res[0]:
            return {"ok": False, "error": res[1].get("error")}
        items = res[1].get("items", [])
        if selected_ids:
            items = [it for it in items if it.get("id") in selected_ids]
        return ops.scan_slaves(client, items)

    return await run_gateway_op(gateway_id, _wrap)


# =====================================================================
# Gestión de archivos
# =====================================================================

@router.get("/{gateway_id}/files/{directory}")
async def gateway_dir(gateway_id: int, directory: str,
                      db: Session = Depends(get_db),
                      current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    directory = directory if directory.endswith('/') else directory + '/'

    def _wrap(client):
        return ops.read_dir(client, directory)

    return await run_gateway_op(gateway_id, _wrap)


@router.get("/{gateway_id}/files/{directory}/{filename}")
async def gateway_download_file(gateway_id: int, directory: str, filename: str,
                                db: Session = Depends(get_db),
                                current_user: User = Depends(get_current_user)):
    _get_gateway(db, gateway_id)
    directory = directory if directory.endswith('/') else directory + '/'

    def _wrap(client):
        res = ops.read_file(client, directory, filename)
        if res.get("ok"):
            res["data_b64"] = base64.b64encode(res.get("data", b"")).decode('ascii')
            res.pop("data", None)
        return res

    return await run_gateway_op(gateway_id, _wrap)


@router.post("/{gateway_id}/files/{directory}/{filename}")
async def gateway_upload_file(gateway_id: int, directory: str, filename: str, data: FileContentIn,
                              db: Session = Depends(get_db),
                              current_user: User = Depends(require_admin)):
    _get_gateway(db, gateway_id)
    directory = directory if directory.endswith('/') else directory + '/'
    content = base64.b64decode(data.data)

    def _wrap(client):
        return ops.write_file(client, directory, filename, content)

    return await run_gateway_op(gateway_id, _wrap)


# =====================================================================
# Helper para construir LoraConf desde flags
# =====================================================================

def _build_lora_from_flags(data: LoraConfWriteIn) -> dict:
    raw = 0
    if data.low_data_rate_opt is not None and data.low_data_rate_opt:
        raw |= 0x00000001
    if data.crc_dis is not None and data.crc_dis:
        raw |= 0x00000002
    if data.explicit_en is not None and data.explicit_en:
        raw |= 0x00000004
    if data.fix_pkln_en is not None and data.fix_pkln_en:
        raw |= 0x00000008
    if data.bandwidth is not None:
        raw |= (int(data.bandwidth) & 0x0F) << 4
    if data.coding_rate is not None:
        raw |= (int(data.coding_rate) & 0x0F) << 8
    if data.sfactor is not None:
        raw |= (int(data.sfactor) & 0x0F) << 12
    if data.tx_pwr is not None:
        raw |= (int(data.tx_pwr) & 0xFF) << 16
    return {
        "raw_bits": raw,
        "pream_length": int(data.pream_length or 0),
        "fixed_pk_length": int(data.fixed_pk_length or 0),
        "frq": int(data.frq or 0),
    }
