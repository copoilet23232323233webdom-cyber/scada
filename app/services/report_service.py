import os
import logging
import socket
import time
import asyncio
from datetime import datetime
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
from app.core.database import SessionLocal
from app.models.plant import Plant
from app.models.gateway import Gateway
from app.models.card import Card

logger = logging.getLogger(__name__)

PUERTO = 502
REG_STATUS = 57624
REG_VOLTAJE = 57625
REG_STRINGS = 57627
NUM_STRINGS = 32
TIMEOUT_MS = 2000
REINTENTOS = 2
DELAY_REINTENTO = 0.2

def modbus_read(ip: str, port: int, unit_id: int, register: int, count: int = 1, timeout: float = 2.0):
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((ip, port))
        pdu = bytes([0x00, 0x01, 0x00, 0x00, 0x00, 0x06, unit_id & 0xFF, 0x03,
                     (register >> 8) & 0xFF, register & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
        sock.sendall(pdu)
        buf = b""
        deadline = time.time() + timeout
        while len(buf) < 9 and time.time() < deadline:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("Cerrado")
            buf += chunk
        if len(buf) < 9:
            raise TimeoutError("Incompleto")
        fc = buf[7]
        if fc & 0x80:
            raise Exception(f"Modbus err FC={fc:02X}")
        byte_count = buf[8]
        total = 9 + byte_count
        while len(buf) < total and time.time() < deadline:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("Cerrado")
            buf += chunk
        regs = []
        for i in range(byte_count // 2):
            o = 9 + i * 2
            raw = (buf[o] << 8) | buf[o + 1]
            if raw >= 0x8000:
                raw -= 0x10000
            regs.append(raw)
        return regs
    finally:
        sock.close()

def leer_voltaje(ip: str, uid: int, timeout: float = 2.0):
    try:
        r = modbus_read(ip, PUERTO, uid, REG_VOLTAJE, 1, timeout)
        return float(r[0])
    except:
        return None

def analizar_diagnostico(status_raw: int):
    fallos = []
    if not ((status_raw >> 5) & 1):
        fallos.append("LoRa FAIL")
    if not ((status_raw >> 9) & 1):
        fallos.append("Mem FAIL")
    return fallos

def leer_strings_caja(ip: str, uid: int, timeout: float = 2.0):
    try:
        r = modbus_read(ip, PUERTO, uid, REG_STRINGS, NUM_STRINGS, timeout)
        return [x / 10.0 for x in r]
    except:
        return None

def analizar_anomalias(corrientes: Optional[List[float]], umbral_pct: float = 30, num_strings: Optional[int] = None):
    if corrientes is None:
        return []
    n = min(int(num_strings), NUM_STRINGS) if num_strings else NUM_STRINGS
    canales = list(range(n))
    activos = [corrientes[i] for i in canales if corrientes[i] > 0.5]
    if len(activos) < 2:
        return []
    media = sum(activos) / len(activos)
    if media < 1.0:
        return []
    umbral_v = media * (umbral_pct / 100.0)
    res = []
    for i in canales:
        c = corrientes[i]
        if c <= 0.5:
            res.append({"string": i + 1, "corriente": c, "media": media, "motivo": f"0.0 A (media:{media:.1f}A)"})
        elif c < umbral_v:
            res.append({"string": i + 1, "corriente": c, "media": media,
                        "motivo": f"{c:.1f}A — {c/media*100:.0f}% de media({media:.1f}A)"})
    return res

def escanear_gateway(ip: str, id_start: int, id_end: int, opts: Dict = None):
    opts = opts or {}
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(TIMEOUT_MS / 1000)
        s.connect((ip, PUERTO))
        s.close()
    except:
        return [{"id": "-", "estado": "SIN CONEXION", "anomalias": [], "alarmas": {},
                 "diag": [], "voltaje": None}]

    resultados = []
    for unit in range(id_start, id_end + 1):
        intento = 0
        ok = False
        while intento < REINTENTOS and not ok:
            try:
                regs = modbus_read(ip, PUERTO, unit, REG_STATUS, 1, TIMEOUT_MS / 1000)
                raw = regs[0]
                bit5 = (raw >> 5) & 1
                estado = "COMUNICACION CORRECTA" if bit5 else "SIN COMUNICACION"

                alarmas = {}
                if opts.get("alarmas") and estado == "COMUNICACION CORRECTA":
                    if not ((raw >> 0) & 1):
                        alarmas["seccionador"] = True
                    if not ((raw >> 1) & 1):
                        alarmas["sobretension"] = True

                diag = []
                if opts.get("diag") and estado == "COMUNICACION CORRECTA":
                    diag = analizar_diagnostico(raw)

                voltaje = None
                if opts.get("voltaje") and estado == "COMUNICACION CORRECTA":
                    voltaje = leer_voltaje(ip, unit, TIMEOUT_MS / 1000)

                anomalias = []
                if opts.get("strings") and estado == "COMUNICACION CORRECTA":
                    corr = leer_strings_caja(ip, unit, TIMEOUT_MS / 1000)
                    anomalias = analizar_anomalias(corr, opts.get("umbral", 30),
                                                   opts.get("strings_map", {}).get(unit))

                resultados.append({"id": unit, "estado": estado, "anomalias": anomalias,
                                   "alarmas": alarmas, "diag": diag, "voltaje": voltaje})
                ok = True
            except:
                intento += 1
                if intento >= REINTENTOS:
                    break
                time.sleep(DELAY_REINTENTO)
    return resultados

def calcular_stats(res_por_gw: Dict, orden: Optional[List] = None) -> Dict:
    ips = orden or list(res_por_gw.keys())
    total = correcta = sin_com = error = sin_cx = 0
    for ip in ips:
        for r in (res_por_gw.get(ip) or []):
            total += 1
            if r["id"] == "-":
                sin_cx += 1
            elif r["estado"] == "COMUNICACION CORRECTA":
                correcta += 1
            elif r["estado"] == "SIN COMUNICACION":
                sin_com += 1
            elif r["estado"] == "ERROR":
                error += 1
            elif r["estado"] == "SIN CONEXION":
                sin_cx += 1
    pok = correcta / total * 100 if total else 0
    pfail = (sin_com + error + sin_cx) / total * 100 if total else 0
    return {"total": total, "correcta": correcta, "sin_com": sin_com,
            "error": error, "sin_conexion": sin_cx, "pct_correcta": pok, "pct_fallo": pfail}

def parse_ips_file(ips_file: str):
    gateways = []
    try:
        with open(ips_file, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if ":" in line:
                    ip_part, range_part = line.split(":", 1)
                    ip = ip_part.strip()
                    if "-" in range_part:
                        id_start, id_end = map(int, range_part.split("-", 1))
                    else:
                        id_start = id_end = int(range_part.strip())
                    gateways.append({"ip": ip, "id_start": id_start, "id_end": id_end})
    except Exception as e:
        logger.error(f"Error parseando {ips_file}: {e}")
    return gateways

async def ejecutar_escaneo_para_reporte(plant_name: str, plant_path: str, opts: Dict = None) -> Dict:
    opts = opts or {}

    # Leer gateways desde la base de datos
    db = SessionLocal()
    try:
        plant = db.query(Plant).filter(Plant.name == plant_name).first()
        if not plant:
            return {"success": False, "error": f"Planta {plant_name} no encontrada"}
        gw_rows = db.query(Gateway).filter(Gateway.plant_id == plant.id).all()
        if not gw_rows:
            return {"success": False, "error": "No hay gateways en la BD"}
        gateways = [{"ip": g.ip, "id_start": g.id_start, "id_end": g.id_end} for g in gw_rows]
    finally:
        db.close()

    res_por_gw = {}
    orden = []

    def run_gw(gw):
        ip = gw["ip"]
        logger.info(f"Escaneando {ip} para reporte...")
        res = escanear_gateway(ip, gw["id_start"], gw["id_end"], opts)
        return ip, res

    with ThreadPoolExecutor(max_workers=10) as ex:
        futures = {ex.submit(run_gw, gw): gw for gw in gateways}
        for f in as_completed(futures):
            ip, res = f.result()
            res_por_gw[ip] = res

    orden = sorted(res_por_gw.keys(), key=lambda ip: tuple(int(x) for x in ip.split('.')))

    stats = calcular_stats(res_por_gw, orden)
    return {
        "success": True,
        "gateways": res_por_gw,
        "orden": orden,
        "stats": stats,
        "plant_name": plant_name
    }
