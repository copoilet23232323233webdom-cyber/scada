"""
Motor Modbus v2 - Con soporte para 5 escaneos y validación de errores
Implementa protocolo Modbus TCP y descubrimiento automático de tarjetas Webdom
"""

import asyncio
import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from app.core.config import settings

logger = logging.getLogger(__name__)

@dataclass
class ModbusScanResult:
    """Resultado de un escaneo Modbus individual"""
    success: bool
    ip: str
    response_time_ms: float
    card_id: int
    firmware: Optional[str] = None
    status_register: Optional[int] = None
    voltage: Optional[float] = None
    lora_ok: bool = False
    communication_ok: bool = False
    sec_alarm: bool = False
    overvoltage_alarm: bool = False
    error_message: Optional[str] = None

@dataclass
class GatewayFinalResult:
    """Resultado final consolidado de 5 escaneos"""
    ip: str
    success: bool
    response_time_ms: float
    firmware: Optional[str]
    total_cards: int
    active_cards: int
    failed_cards: int
    lora_ok: bool
    cards: List[Dict]
    per_scan_time_ms: float = 0
    error_message: Optional[str] = None
    scan_history: List[Dict] = None

class ModbusServiceV2:
    """
    Servicio Modbus mejorado:
    - Protocolo Modbus TCP puro
    - Descubrimiento automático de tarjetas (GETCBTB equivalente)
    - 5 escaneos por Gateway para validación
    - Soporte para alarmas (SEC, Sobretensión, Comunicación)
    """
    
    # Registros Modbus Webdom
    REG_STATUS = 57624          # Estado general
    REG_VOLTAGE = 57625         # Voltaje
    REG_TEMP = 57626            # Temperatura
    REG_STRINGS = 57627         # Strings
    
    # Bits de estado (registro 57624) - SSX EVO Modbus Map rev.A.20.10.2022
    BIT_DIGITAL_IN1 = 0         # Bit 0: Digital In 1 (1=ok, 0=fail) -> SEC seccionador
    BIT_DIGITAL_IN2 = 1         # Bit 1: Digital In 2 (1=ok, 0=fail) -> Sobretensión
    BIT_LORA_OK = 5             # Bit 5: LoRa OK (1=ok, 0=fail)
    BIT_MEM_FAIL = 9            # Bit 9: Fallo memoria
    
    # Configuración
    TIMEOUT_MS = 2000
    RETRIES = 1
    DELAY_RETRY_MS = 200
    SCAN_COUNT = 1              # 1 escaneo (rápido, los gateways responden bien)
    
    def __init__(self):
        self.timeout = settings.MODBUS_TIMEOUT
        self.port = settings.MODBUS_PORT
        self.scan_cache = {}
        self.ssh_transport = None
        # Executor DEDICADO y acotado para Modbus. Evita que las lecturas TCP con
        # timeout a gateways inaccesibles saturen el pool global (que sirve auth/DB/
        # health), y así el servidor nunca se queda "bloqueado".
        self._executor = ThreadPoolExecutor(
            max_workers=settings.MODBUS_MAX_WORKERS, thread_name_prefix='modbus'
        )

    def set_ssh_transport(self, transport):
        self.ssh_transport = transport

    async def _tcp_precheck(self, ip: str, timeout: float = 2.0) -> bool:
        """Comprueba rápidamente si el gateway acepta TCP en el puerto Modbus.
        Si no responde en ~2s, no vale la pena hacer el escaneo secuencial (32×2s)."""
        def _check():
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                result = sock.connect_ex((ip, self.port))
                return result == 0
            finally:
                sock.close()
        try:
            loop = asyncio.get_event_loop()
            ok = await asyncio.wait_for(loop.run_in_executor(self._executor, _check), timeout=timeout + 1)
            return ok
        except Exception:
            return False
    
    def _crc16(self, data: bytes) -> bytes:
        """Calcula CRC16 Modbus"""
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return bytes([(crc & 0xFF), (crc >> 8) & 0xFF])
    
    def _build_modbus_request(self, unit_id: int, register: int, count: int = 1) -> bytes:
        """Construye una petición Modbus TCP"""
        transaction_id = 0x0001
        protocol_id = 0x0000
        length = 6
        function_code = 0x03  # Read Holding Registers
        
        pdu = bytes([unit_id, function_code, 
                    (register >> 8) & 0xFF, register & 0xFF,
                    (count >> 8) & 0xFF, count & 0xFF])
        
        mbap = bytes([
            (transaction_id >> 8) & 0xFF, transaction_id & 0xFF,
            (protocol_id >> 8) & 0xFF, protocol_id & 0xFF,
            (length >> 8) & 0xFF, length & 0xFF
        ])
        
        return mbap + pdu
    
    def _parse_modbus_response(self, response: bytes) -> Optional[List[int]]:
        """Parsea respuesta Modbus TCP"""
        if len(response) < 9:
            return None
        
        # Verificar función
        if response[7] & 0x80:  # Error
            return None
        
        byte_count = response[8]
        if len(response) < 9 + byte_count:
            return None
        
        # Extraer registros
        registers = []
        for i in range(0, byte_count, 2):
            hi = response[9 + i]
            lo = response[9 + i + 1]
            reg = (hi << 8) | lo
            if reg >= 0x8000:
                reg -= 0x10000
            registers.append(reg)
        
        return registers
    
    async def modbus_read_async(self, ip: str, unit_id: int, register: int, 
                                count: int = 1, timeout: float = None) -> Optional[List[int]]:
        """Lee registros Modbus de forma asincrónica"""
        if timeout is None:
            timeout = self.TIMEOUT_MS / 1000.0
        
        loop = asyncio.get_event_loop()
        
        def _read_socket(sock):
            request = self._build_modbus_request(unit_id, register, count)
            sock.sendall(request)
            response = b""
            start_time = time.time()
            while len(response) < 9 and (time.time() - start_time) < timeout:
                chunk = sock.recv(1024)
                if not chunk:
                    raise ConnectionError("Conexión cerrada por servidor")
                response += chunk
            if len(response) < 9:
                raise TimeoutError("Respuesta incompleta")
            byte_count = response[8]
            while len(response) < (9 + byte_count) and (time.time() - start_time) < timeout:
                chunk = sock.recv(1024)
                if not chunk:
                    break
                response += chunk
            return self._parse_modbus_response(response)
        
        def _read():
            # Intentar usar canal SSH si está disponible
            if self.ssh_transport and self.ssh_transport.is_active():
                try:
                    channel = self.ssh_transport.open_channel(
                        'direct-tcpip',
                        (ip, self.port),
                        ('', 0)
                    )
                    if channel:
                        channel.settimeout(timeout)
                        try:
                            result = _read_socket(channel)
                            return result
                        finally:
                            channel.close()
                except Exception as e:
                    logger.debug(f"SSH channel error {ip}@{unit_id}: {e}, fallback a TCP directo")
            
            # Fallback: conexión TCP directa
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            try:
                sock.connect((ip, self.port))
                return _read_socket(sock)
            finally:
                sock.close()
        
        try:
            return await loop.run_in_executor(self._executor, _read)
        except Exception as e:
            logger.debug(f"Modbus error {ip}@{unit_id}: {e}")
            return None
    
    async def discover_cards(self, ip: str, id_start: int, id_end: int, 
                           timeout: float = None) -> List[int]:
        """Descubre las tarjetas que responden en un Gateway."""
        cards = await self.probe_cards(ip, id_start, id_end, timeout)
        return [c['modbus_id'] for c in cards]

    def _decode_card(self, card_id: int, status_reg: int, voltage_reg: Optional[int],
                     elapsed_ms: float) -> Dict:
        """Traduce los registros crudos de una tarjeta a su estado."""
        lora_ok = bool((status_reg >> self.BIT_LORA_OK) & 1)
        return {
            "modbus_id": card_id,
            "success": True,
            "communication_ok": True,
            "lora_ok": lora_ok,
            "sec_alarm": not bool((status_reg >> self.BIT_DIGITAL_IN1) & 1),
            "overvoltage_alarm": not bool((status_reg >> self.BIT_DIGITAL_IN2) & 1),
            "voltage": (float(voltage_reg) / 10.0) if voltage_reg is not None else None,
            "response_time_ms": elapsed_ms,
            "error": None,
        }

    async def _probe_card(self, ip: str, card_id: int, timeout: float,
                          count: int = 2) -> Optional[Dict]:
        """Sondea una tarjeta con UNA sola lectura (estado + voltaje contiguos).

        Antes se hacía un descubrimiento y después otra pasada leyendo cada
        tarjeta otra vez, lo que doblaba el número de conexiones TCP.
        """
        started = time.time()
        regs = await self.modbus_read_async(ip, card_id, self.REG_STATUS, count, timeout)
        if not regs:
            return None
        voltage = regs[1] if len(regs) >= 2 else None
        return self._decode_card(card_id, regs[0], voltage,
                                 (time.time() - started) * 1000)

    async def _probe_pass(self, ip: str, ids: List[int], timeout: float, count: int,
                          budget: float, progress_cb=None, done_offset: int = 0,
                          total: int = None) -> List[Dict]:
        """Una pasada paralela de sondas acotada por `budget` segundos."""
        total = total or len(ids)
        sem = asyncio.Semaphore(settings.MODBUS_GATEWAY_CONCURRENCY)
        done = done_offset

        async def probe(card_id: int) -> Optional[Dict]:
            nonlocal done
            async with sem:
                try:
                    card = await self._probe_card(ip, card_id, timeout, count)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    card = None
            done += 1
            if progress_cb:
                try:
                    progress_cb(min(done, total), total)
                except Exception:
                    pass
            return card

        tasks = [asyncio.ensure_future(probe(cid)) for cid in ids]
        finished, pending = await asyncio.wait(tasks, timeout=max(0.5, budget))
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
            logger.warning(
                f"Gateway {ip}: {len(pending)}/{len(ids)} sondas canceladas por presupuesto ({budget:.1f}s)"
            )

        return [t.result() for t in finished
                if not t.cancelled() and t.exception() is None and t.result() is not None]

    async def probe_cards(self, ip: str, id_start: int, id_end: int,
                          timeout: float = None, progress_cb=None,
                          budget: float = None) -> List[Dict]:
        """Sondea en paralelo todos los IDs y devuelve las tarjetas presentes.

        `progress_cb(done, total)` se invoca según van terminando las sondas y
        `budget` acota la duración total: lo que no haya respondido a tiempo se
        cancela en vez de dejar el escaneo colgado.
        """
        timeout = timeout or settings.MODBUS_PROBE_TIMEOUT
        budget = budget or settings.SCAN_GATEWAY_BUDGET_SECONDS
        started = time.time()
        ids = list(range(id_start, id_end + 1))
        total = len(ids)

        cards = await self._probe_pass(ip, ids, timeout, 2, budget,
                                       progress_cb=progress_cb, total=total)

        # Algunos gateways rechazan leer 2 registros de golpe: si NO ha respondido
        # nadie, se repite la pasada con lectura simple (una sola vez, no por ID).
        remaining = budget - (time.time() - started)
        if not cards and remaining > 1.0:
            logger.info(f"Gateway {ip}: sin respuesta con lectura doble, reintento simple")
            cards = await self._probe_pass(ip, ids, timeout, 1, remaining, total=total)
        return sorted(cards, key=lambda c: c['modbus_id'])
    
    async def scan_card(self, ip: str, card_id: int, timeout: float = None) -> ModbusScanResult:
        """Escanea una tarjeta individual y retorna todos sus parámetros"""
        start_time = time.time()
        
        result = ModbusScanResult(
            success=False,
            ip=ip,
            response_time_ms=0,
            card_id=card_id,
            firmware=None,
            status_register=None
        )
        
        try:
            # Leer registro de estado
            regs = await self.modbus_read_async(ip, card_id, self.REG_STATUS, 1, timeout)
            if not regs:
                result.error_message = "No responde"
                return result
            
            status_reg = regs[0]
            result.status_register = status_reg
            result.communication_ok = True
            
            # Analizar bits de estado (SSX EVO Modbus Map)
            # Bit 0: Digital In 1 (1=ok, 0=fail) - SEC seccionador abierto
            # Bit 1: Digital In 2 (1=ok, 0=fail) - Sobretensión
            # Bit 5: LoRa OK (1=ok, 0=fail)
            result.lora_ok = bool((status_reg >> self.BIT_LORA_OK) & 1)
            result.sec_alarm = not bool((status_reg >> self.BIT_DIGITAL_IN1) & 1)
            result.overvoltage_alarm = not bool((status_reg >> self.BIT_DIGITAL_IN2) & 1)
            
            # Leer voltaje
            if result.lora_ok:
                try:
                    v_regs = await self.modbus_read_async(ip, card_id, self.REG_VOLTAGE, 1, timeout)
                    if v_regs:
                        result.voltage = float(v_regs[0]) / 10.0
                except:
                    pass
            
            result.success = True
            result.response_time_ms = (time.time() - start_time) * 1000
            
        except Exception as e:
            result.error_message = str(e)
        
        return result
    
    async def scan_gateway_multi(self, ip: str, id_start: int, id_end: int,
                                timeout: float = None, progress_cb=None) -> GatewayFinalResult:
        """Escanea un gateway en una sola pasada paralela y acotada en tiempo."""
        if timeout is None:
            timeout = settings.MODBUS_PROBE_TIMEOUT

        start_time = time.time()
        
        # Fail-fast: si el gateway no acepta TCP (~2s), no hacer el escaneo
        # secuencial de 32 IDs × 2s = 64s. Devuelve al instante como unreachable.
        if not await self._tcp_precheck(ip, timeout=min(2.0, timeout)):
            logger.info(f"Gateway {ip}: sin respuesta TCP, fail-fast (sin escaneo 64s)")
            return GatewayFinalResult(
                ip=ip,
                success=False,
                response_time_ms=(time.time() - start_time) * 1000,
                firmware=None,
                total_cards=id_end - id_start + 1,
                active_cards=0,
                failed_cards=id_end - id_start + 1,
                lora_ok=False,
                cards=[],
                error_message="Gateway inaccesible (sin respuesta TCP)"
            )
        
        remaining = max(1.0, settings.SCAN_GATEWAY_BUDGET_SECONDS - (time.time() - start_time))
        cards = await self.probe_cards(ip, id_start, id_end, timeout,
                                       progress_cb=progress_cb, budget=remaining)
        duration_ms = (time.time() - start_time) * 1000

        scan_results = [{
            "scan_number": 1,
            "timestamp": time.time(),
            "active_cards": len(cards),
            "cards": cards,
            "duration_ms": duration_ms,
            "success": len(cards) > 0,
        }]

        final_result = self._consolidate_scans(ip, scan_results)
        final_result.response_time_ms = duration_ms
        final_result.per_scan_time_ms = duration_ms
        if not cards:
            final_result.error_message = "Ninguna tarjeta respondio"
        return final_result
    
    def _consolidate_scans(self, ip: str, scan_results: List[Dict]) -> GatewayFinalResult:
        """
        Consolida 5 escaneos:
        - Si todos coinciden: aceptar resultado
        - Si hay diferencias: usar resultado más frecuente
        - Detectar errores consistentes
        """
        result = GatewayFinalResult(
            ip=ip,
            success=False,
            response_time_ms=0,
            firmware=None,
            total_cards=0,
            active_cards=0,
            failed_cards=0,
            lora_ok=False,
            cards=[],
            scan_history=scan_results
        )
        
        # Contar tarjetas detectadas en cada escaneo
        card_counts = [len(sr['cards']) for sr in scan_results]
        most_common_count = max(set(card_counts), key=card_counts.count)
        
        # Si los 5 escaneos coinciden, confiar en el resultado
        if len(set(card_counts)) == 1:
            result.total_cards = most_common_count
            if scan_results[0]['success']:
                result.cards = scan_results[0]['cards']
                result.active_cards = len([c for c in result.cards if c['communication_ok']])
                result.failed_cards = most_common_count - result.active_cards
                result.success = True
                result.lora_ok = all(c.get('lora_ok', False) for c in result.cards)
        else:
            # Si hay variación, usar el más frecuente
            result.total_cards = most_common_count
            result.success = True  # Al menos se puede comunicar
            
            # Usar datos del último escaneo exitoso
            for sr in reversed(scan_results):
                if sr['success']:
                    result.cards = sr['cards']
                    result.active_cards = len([c for c in result.cards if c['communication_ok']])
                    result.failed_cards = most_common_count - result.active_cards
                    break
        
        return result
    
    async def scan_gateway(self, ip: str, id_start: int = 1, id_end: int = 32,
                           progress_cb=None) -> Dict:
        """Escaneo completo de un gateway (interfaz usada por el scan service)."""
        result = await self.scan_gateway_multi(ip, id_start, id_end,
                                               progress_cb=progress_cb)
        
        # Use max card response time as gateway response_time.
        # The per_scan_time_ms is the total discovery+scan duration (~20-60s for many cards),
        # which is NOT the Modbus latency. Individual card responses are ~600-700ms.
        card_times = [c.get('response_time_ms', 0) for c in result.cards if c.get('response_time_ms', 0) > 0]
        max_card_time = max(card_times) if card_times else 0
        
        return {
            "ip": ip,
            "success": result.success,
            "response_time": int(max_card_time),
            "full_scan_time_ms": int(result.response_time_ms),
            "per_scan_time_ms": int(result.per_scan_time_ms),
            "lora_ok": result.lora_ok,
            "cards": result.cards,
            "total_cards": result.total_cards,
            "active_cards": result.active_cards,
            "failed_cards": result.failed_cards,
            "error": result.error_message,
            "scan_history": result.scan_history
        }

# Instancia global
modbus_service = ModbusServiceV2()
