from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from typing import List
import json
import asyncio
import logging
from app.websocket.manager import ws_manager

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/status")
async def websocket_endpoint(websocket: WebSocket):
    """Endpoint WebSocket para actualizaciones en tiempo real"""
    conn_id = await ws_manager.connect(websocket)
    try:
        # Mantener conexión viva, escuchando mensajes del cliente
        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                # Ping/pong para mantener conexión viva
                if msg.get("type") == "ping":
                    await websocket.send_json({"type": "pong"})
                # El cliente puede solicitar datos específicos
                elif msg.get("type") == "subscribe":
                    await websocket.send_json({
                        "type": "subscribed",
                        "data": {"channel": msg.get("channel")}
                    })
            except json.JSONDecodeError:
                pass
    except WebSocketDisconnect:
        ws_manager.disconnect(websocket)
        logger.info(f"Cliente WebSocket desconectado (ID: {conn_id})")
    except Exception as e:
        logger.error(f"Error en WebSocket: {e}")
        ws_manager.disconnect(websocket)

async def broadcast_update(update_type: str, data: dict):
    """Función helper para broadcast de actualizaciones"""
    await ws_manager.broadcast({"type": update_type, "data": data})
