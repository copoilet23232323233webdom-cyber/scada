"""Gateway Modbus TCP simulado para probar el escaneo en local.

Uso: python scripts/dev/fake_gateway.py [puerto] [ids_activos]
Ejemplo: python scripts/dev/fake_gateway.py 5020 1,2,3,7
"""
import socket
import socketserver
import sys
import threading
import time

ACTIVE_IDS = {1, 2, 3}
LATENCY = 0.05


class Handler(socketserver.BaseRequestHandler):
    def handle(self):
        self.request.settimeout(5)
        while True:
            try:
                data = self.request.recv(1024)
            except OSError:
                return
            if not data or len(data) < 12:
                return
            unit_id = data[6]
            count = (data[10] << 8) | data[11]
            time.sleep(LATENCY)
            if unit_id not in ACTIVE_IDS:
                continue  # el gateway no contesta por IDs inexistentes
            payload = b""
            for i in range(count):
                value = 0x0023 if i == 0 else 2350  # estado con LoRa OK / 235.0 V
                payload += bytes([(value >> 8) & 0xFF, value & 0xFF])
            body = bytes([unit_id, 0x03, len(payload)]) + payload
            mbap = bytes([0, 1, 0, 0, (len(body) >> 8) & 0xFF, len(body) & 0xFF])
            try:
                self.request.sendall(mbap + body)
            except OSError:
                return


class Server(socketserver.ThreadingTCPServer):
    allow_reuse_address = True
    daemon_threads = True


def serve(port: int) -> Server:
    server = Server(("127.0.0.1", port), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 5020
    if len(sys.argv) > 2:
        ACTIVE_IDS = {int(x) for x in sys.argv[2].split(",")}
    serve(port)
    print(f"Fake gateway en 127.0.0.1:{port} ids={sorted(ACTIVE_IDS)}")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
