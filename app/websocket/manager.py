"""
WebSocket Manager - Gestiona conexiones en tiempo real
Broadcast de escaneos, alarmas y estado del sistema
"""

from fastapi import WebSocket, WebSocketDisconnect
from typing import List, Dict, Any
import json
import asyncio
import logging

logger = logging.getLogger(__name__)

class WebSocketManager:
    """
    Gestor de conexiones WebSocket:
    - Mantiene lista de conexiones activas
    - Broadcast de eventos en tiempo real
    - Auto-limpieza de conexiones caídas
    """
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_info: Dict[int, dict] = {}  # id -> {client, connected_at}
        self._id_counter = 0
    
    async def connect(self, websocket: WebSocket) -> int:
        """Acepta nueva conexión WebSocket y retorna ID"""
        await websocket.accept()
        self._id_counter += 1
        conn_id = self._id_counter
        self.active_connections.append(websocket)
        self.connection_info[conn_id] = {
            "client": websocket.client,
            "connected_at": asyncio.get_event_loop().time()
        }
        logger.info(f"WebSocket conectado: {websocket.client} (ID: {conn_id})")
        
        # Enviar mensaje de bienvenida
        await websocket.send_json({
            "type": "connected",
            "data": {
                "connection_id": conn_id,
                "message": "Conectado a Webdom Monitor"
            }
        })
        
        return conn_id
    
    def disconnect(self, websocket: WebSocket):
        """Elimina conexión WebSocket"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        # Limpiar connection_info
        for conn_id, info in list(self.connection_info.items()):
            if info.get("client") == websocket.client:
                del self.connection_info[conn_id]
        logger.info(f"WebSocket desconectado: {websocket.client}")
    
    async def broadcast(self, message: dict):
        """Envía mensaje a TODAS las conexiones activas"""
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.warning(f"Error enviando WebSocket: {e}")
                disconnected.append(connection)
        
        # Limpiar conexiones caídas
        for conn in disconnected:
            self.disconnect(conn)
    
    async def broadcast_scan_update(self, plant_name: str, gateway_ip: str, 
                                     status: str, total_cards: int, 
                                     active_cards: int, failed_cards: int,
                                     response_time_ms: float = None):
        """Broadcast de actualización de escaneo"""
        await self.broadcast({
            "type": "scan_update",
            "data": {
                "plant_name": plant_name,
                "gateway_ip": gateway_ip,
                "status": status,
                "total_cards": total_cards,
                "active_cards": active_cards,
                "failed_cards": failed_cards,
                "response_time_ms": response_time_ms,
                "timestamp": asyncio.get_event_loop().time()
            }
        })
    
    async def broadcast_alarm(self, alarm_data: dict):
        """Broadcast de nueva alarma"""
        await self.broadcast({
            "type": "alarm",
            "data": alarm_data
        })
    
    async def broadcast_plant_status(self, plant_data: dict):
        """Broadcast de cambio de estado de planta"""
        await self.broadcast({
            "type": "plant_status",
            "data": plant_data
        })
    
    async def broadcast_scheduler_status(self, status_data: dict):
        """Broadcast de estado del scheduler"""
        await self.broadcast({
            "type": "scheduler_status",
            "data": status_data
        })
    
    def get_connection_count(self) -> int:
        """Retorna número de conexiones activas"""
        return len(self.active_connections)

# Instancia global
ws_manager = WebSocketManager()