"""
Codecs y conversiones replicados de Utils.cs / GWitem.cs / CBitem.cs / loraConf.cs
del proyecto multi_gw_control (C#). Convierten entre registros Modbus (ushort) y
valores de alto nivel (float, MAC, clave LoRa, configuracion LoRa, sysConf, etc.)
"""
import struct
from typing import List


def ushorts_to_float(u1: int, u2: int) -> float:
    """Replica Utils.ushortsToFloat(u1, u2)."""
    b = bytearray(4)
    b[3] = (u2 >> 8) & 0xFF
    b[2] = u2 & 0xFF
    b[1] = (u1 >> 8) & 0xFF
    b[0] = u1 & 0xFF
    return struct.unpack('<f', bytes(b))[0]


def float_to_ushorts(value: float):
    """Replica Utils.floatToUshorts. Devuelve (u1, u2)."""
    b = struct.pack('<f', value)
    u1 = (b[1] << 8 | b[0]) & 0xFFFF
    u2 = (b[3] << 8 | b[2]) & 0xFFFF
    return u1, u2


def encode_float_to_regs(value: float):
    """Devuelve lista de 2 registros ushort codificando un float."""
    u1, u2 = float_to_ushorts(value)
    return [u1, u2]


def decode_regs_to_float(regs, idx: int) -> float:
    """Decodifica float desde regs[idx], regs[idx+1]."""
    return ushorts_to_float(regs[idx], regs[idx + 1])


def hex_to_bytearray(hexstr: str) -> bytearray:
    """Replica Utils.ConvertToByteArray (acepta '0x' opcional, rellena impar con 0)."""
    hexstr = (hexstr or '').strip()
    if not hexstr:
        return bytearray()
    start = 2 if hexstr.lower().startswith('0x') else 0
    body = hexstr[start:]
    if len(body) % 2 != 0:
        body = '0' + body
    return bytearray(bytes.fromhex(body))


def mac_str_to_bytes(mac: str) -> bytes:
    """Convierte una MAC 'XX.XX.XX.XX.XX.XX.XX.XX' a bytes (con puntos o sin)."""
    cleaned = mac.replace('.', '').replace(':', '')
    return hex_to_bytearray(cleaned)


def bytes_to_mac_str(data) -> str:
    """Formatea 8 bytes a 'XX.XX.XX.XX.XX.XX.XX.XX' (orden igual que GWitem)."""
    d = bytes(data)
    return "{0:02X}.{1:02X}.{2:02X}.{3:02X}.{4:02X}.{5:02X}.{6:02X}.{7:02X}".format(
        d[0], d[1], d[2], d[3], d[4], d[5], d[6], d[7]
    )


def key_bytes_to_str(key: bytearray) -> str:
    """Formatea la clave de 16 bytes a string hex (igual que CBitem.key setter, reversed)."""
    if not key or len(key) < 16:
        return ""
    k = bytes(key)
    return "{0:02X}{1:02X}{2:02X}{3:02X}{4:02X}{5:02X}{6:02X}{7:02X}{8:02X}{9:02X}{10:02X}{11:02X}{12:02X}{13:02X}{14:02X}{15:02X}".format(
        k[15], k[14], k[13], k[12], k[11], k[10], k[9], k[8],
        k[7], k[6], k[5], k[4], k[3], k[2], k[1], k[0]
    )


def key_str_to_bytes(keystr: str) -> bytearray:
    """Convierte string hex de 32 caracteres a bytes de 16, invirtiendo el orden."""
    raw = hex_to_bytearray(keystr)
    if len(raw) < 16:
        raw = bytearray(16 - len(raw)) + raw
    return bytearray(reversed(bytes(raw[:16])))


# ------------------------------------------------------------------
# Configuracion LoRa (rawBits de 32 bits + PreamLength + FixedPkLength + Frq)
# ------------------------------------------------------------------

class LoraConf:
    def __init__(self, raw_bits: int = 0, pream_length: int = 0,
                 fixed_pk_length: int = 0, frq: int = 0, lora_id: int = 0):
        self.raw_bits = raw_bits & 0xFFFFFFFF
        self.pream_length = pream_length
        self.fixed_pk_length = fixed_pk_length
        self.frq = frq & 0xFFFFFFFF
        self.lora_id = lora_id

    # --- propiedades derivadas de rawBits ---
    @property
    def low_data_rate_opt(self) -> bool:
        return bool(self.raw_bits & 0x00000001)

    @property
    def crc_dis(self) -> bool:
        return bool(self.raw_bits & 0x00000002)

    @property
    def explicit_en(self) -> bool:
        return bool(self.raw_bits & 0x00000004)

    @property
    def fix_pkln_en(self) -> bool:
        return bool(self.raw_bits & 0x00000008)

    @property
    def bandwidth(self) -> int:
        return (self.raw_bits >> 4) & 0x0F

    @property
    def coding_rate(self) -> int:
        return (self.raw_bits >> 8) & 0x0F

    @property
    def sfactor(self) -> int:
        return (self.raw_bits >> 12) & 0x0F

    @property
    def tx_pwr(self) -> int:
        return (self.raw_bits >> 16) & 0xFF

    def set_rawbit_field(self, mask_set, mask_clear_mask, value_bits, value):
        self.raw_bits &= mask_clear_mask
        self.raw_bits |= (value << value_bits)
        self.raw_bits &= 0xFFFFFFFF

    def as_dict(self) -> dict:
        return {
            "raw_bits": self.raw_bits,
            "pream_length": self.pream_length,
            "fixed_pk_length": self.fixed_pk_length,
            "frq": self.frq,
            "lora_id": self.lora_id,
            "low_data_rate_opt": self.low_data_rate_opt,
            "crc_dis": self.crc_dis,
            "explicit_en": self.explicit_en,
            "fix_pkln_en": self.fix_pkln_en,
            "bandwidth": self.bandwidth,
            "coding_rate": self.coding_rate,
            "sfactor": self.sfactor,
            "tx_pwr": self.tx_pwr,
        }

    def to_registers(self) -> List[int]:
        """6 registros en el formato que escribe el multiGW (SLV_LORA_CONFIG)."""
        return [
            self.raw_bits & 0xFFFF,
            (self.raw_bits >> 16) & 0xFFFF,
            self.pream_length & 0xFFFF,
            self.fixed_pk_length & 0xFFFF,
            self.frq & 0xFFFF,
            (self.frq >> 16) & 0xFFFF,
        ]


def decode_lora_conf(regs: List[int]):
    """Decodifica 10 registros SLV_LORA_CONFIG en un LoraConf."""
    raw_bits = ((regs[1] & 0xFFFF) << 16) | (regs[0] & 0xFFFF)
    pream = regs[2]
    fixed_pk = regs[3]
    frq = ((regs[5] & 0xFFFF) << 16) | (regs[4] & 0xFFFF)
    lora_id = 0
    if len(regs) >= 10:
        lora_id = ((regs[9] & 0xFFFFFFFF) << 48) | ((regs[8] & 0xFFFFFFFF) << 32) | \
                  ((regs[7] & 0xFFFFFFFF) << 16) | (regs[6] & 0xFFFFFFFF)
    return LoraConf(raw_bits, pream, fixed_pk, frq, lora_id)


# ------------------------------------------------------------------
# Configuracion de sistema del slave (SysConfCB.config de 32 bits)
# ------------------------------------------------------------------

SYS_BIT_ENABLE_485 = 0x00000001
SYS_BIT_ENABLE_SERIAL = 0x00000002
SYS_BIT_ENABLE_LORA = 0x00000004
SYS_BIT_ENABLE_HV = 0x00000008
SYS_BIT_SLAVE_ENABLE = 0x00000010
SYS_BIT_ENABLE_DLOG = 0x00000020
SYS_BIT_ENABLE_CHARGER = 0x00000040
SYS_BIT_ENCRYPT_485 = 0x00000800
SYS_BIT_ENCRYPT_SERIAL = 0x00001000
SYS_BIT_ENCRYPT_LORA = 0x00002000
SYS_BIT_CHIP_ID = 0x00004000
SYS_BIT_FIRST_CFG = 0x00008000
SYS_BIT_CUSTOM_MAC = 0x00010000


def sys_config_flags(config: int) -> dict:
    c = config & 0xFFFFFFFF
    return {
        "config": c,
        "enable_485": bool(c & SYS_BIT_ENABLE_485),
        "enable_serial": bool(c & SYS_BIT_ENABLE_SERIAL),
        "enable_lora": bool(c & SYS_BIT_ENABLE_LORA),
        "enable_hv": bool(c & SYS_BIT_ENABLE_HV),
        "slave_enable": bool(c & SYS_BIT_SLAVE_ENABLE),
        "enable_dlog": bool(c & SYS_BIT_ENABLE_DLOG),
        "enable_charger": bool(c & SYS_BIT_ENABLE_CHARGER),
        "encrypt_485": bool(c & SYS_BIT_ENCRYPT_485),
        "encrypt_serial": bool(c & SYS_BIT_ENCRYPT_SERIAL),
        "encrypt_lora": bool(c & SYS_BIT_ENCRYPT_LORA),
        "chip_id": bool(c & SYS_BIT_CHIP_ID),
        "first_cfg": bool(c & SYS_BIT_FIRST_CFG),
        "custom_mac": bool(c & SYS_BIT_CUSTOM_MAC),
        "zlimit": (c >> 24) & 0xFF,
    }


# ------------------------------------------------------------------
# Configuracion de comunicacion (CommSett) por canal
# ------------------------------------------------------------------

def decode_comm_conf(regs: List[int], base_idx: int) -> dict:
    """Decodifica CommSett[i] desde regs[base_idx .. base_idx+5] (6 registros)."""
    r = regs
    return {
        "slave_id": r[0 + base_idx],
        "timeout": r[1 + base_idx],
        "baudrate": ((r[3 + base_idx] & 0xFFFF) << 16) | (r[2 + base_idx] & 0xFFFF),
        "char_len": r[4 + base_idx] & 0x000F,
        "parity": (r[4 + base_idx] & 0x0FF0) >> 4,
        "stop_bit": (r[4 + base_idx] & 0x3000) >> 12,
        "id_ovr": bool(r[5 + base_idx] & 0x0020),
    }


def encode_comm_conf(comm: dict) -> List[int]:
    """Codifica un CommSett en 6 registros."""
    baud = comm.get('baudrate', 0) & 0xFFFFFFFF
    char_len = comm.get('char_len', 0) & 0x0F
    parity = comm.get('parity', 0) & 0x0F
    stop = comm.get('stop_bit', 0) & 0x3
    id_ovr = 0x20 if comm.get('id_ovr', False) else 0
    return [
        comm.get('slave_id', 0) & 0xFFFF,
        comm.get('timeout', 0) & 0xFFFF,
        baud & 0xFFFF,
        (baud >> 16) & 0xFFFF,
        (char_len | (parity << 4) | (stop << 12)) & 0xFFFF,
        id_ovr,
    ]


# ------------------------------------------------------------------
# Mapa de canales MUX (ChannelItem: toroide -> channel)
# 16 registros, cada uno codifica 2 canales (par en byte bajo, impar en byte alto)
# ------------------------------------------------------------------

def decode_channel_map(regs: List[int]) -> List[dict]:
    result = []
    for i in range(16):
        v = regs[i]
        result.append({"toroide": 2 * i, "channel": v & 0xFF})
        result.append({"toroide": 2 * i + 1, "channel": (v >> 8) & 0xFF})
    return result


def encode_channel_map(channels: List[int]) -> List[int]:
    """channels: lista de 32 enteros (channel por toroide 0..31)."""
    regs = []
    for i in range(16):
        lo = channels[2 * i] & 0xFF
        hi = channels[2 * i + 1] & 0xFF
        regs.append((hi << 8) | lo)
    return regs


# ------------------------------------------------------------------
# Aes-ECB (replica de Crypto.cs con Rijndael, BlockSize 128, Padding Zeros)
# ------------------------------------------------------------------
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes  # noqa: E402

_AES = None


def _get_aes():
    global _AES
    if _AES is None:
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
            _AES = True
        except Exception:
            _AES = False
    return _AES


def decrypt_bytes(data: bytes, key: bytes) -> bytes:
    if not _get_aes():
        raise RuntimeError("Lib 'cryptography' no disponible para AES")
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    decryptor = cipher.decryptor()
    # PaddingMode.Zeros: simplemente descifra el bloque (datos multiplo de 16)
    dec = decryptor.update(data) + decryptor.finalize()
    return dec


def encrypt_bytes(data: bytes, key: bytes) -> bytes:
    if not _get_aes():
        raise RuntimeError("Lib 'cryptography' no disponible para AES")
    # alinear a multiplo de 16 con ceros (PaddingMode.Zeros)
    padded = data + b'\x00' * ((16 - len(data) % 16) % 16)
    cipher = Cipher(algorithms.AES(key), modes.ECB())
    encryptor = cipher.encryptor()
    return encryptor.update(padded) + encryptor.finalize()
