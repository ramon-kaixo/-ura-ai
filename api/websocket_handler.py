#!/usr/bin/env python3
"""
URA WebSocket Handler - Real-time features
"""

import asyncio
import json
from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger
from fastapi import WebSocket

logger = get_logger("websocket_handler", log_dir="./logs")


class ConnectionManager:
    """Gestor de conexiones WebSocket"""

    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.connection_metadata: dict[WebSocket, dict[str, Any]] = {}

    async def connect(self, websocket: WebSocket, client_id: str = None):
        """Aceptar nueva conexión"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "client_id": client_id,
            "connected_at": datetime.now(tz=UTC).isoformat(),
        }
        logger.info(f"WebSocket conectado: {client_id}")

    def disconnect(self, websocket: WebSocket):
        """Desconectar cliente"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_metadata:
            client_id = self.connection_metadata[websocket].get("client_id")
            del self.connection_metadata[websocket]
            logger.info(f"WebSocket desconectado: {client_id}")

    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Enviar mensaje a un cliente específico"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            logger.error(f"Error enviando mensaje: {e}")

    async def broadcast(self, message: str):
        """Broadcast mensaje a todos los clientes conectados"""
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error en broadcast: {e}")
                disconnected.append(connection)

        # Limpiar conexiones desconectadas
        for conn in disconnected:
            self.disconnect(conn)

    async def broadcast_json(self, data: dict[str, Any]):
        """Broadcast mensaje JSON a todos los clientes"""
        await self.broadcast(json.dumps(data))

    def get_connection_count(self) -> int:
        """Obtener número de conexiones activas"""
        return len(self.active_connections)


# Instancia global
manager = ConnectionManager()


class WebSocketHandler:
    """Handler de mensajes WebSocket"""

    @staticmethod
    async def handle_chat_message(websocket: WebSocket, data: dict[str, Any]):
        """Manejar mensaje de chat"""
        message = data.get("message", "")
        model = data.get("model", "llama3.2:1b")

        # Procesar mensaje (simulado)
        response = {
            "type": "chat_response",
            "message": f"Respuesta para: {message}",
            "model": model,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        await manager.send_personal_message(json.dumps(response), websocket)

    @staticmethod
    async def handle_metrics_request(websocket: WebSocket):
        """Manejar solicitud de métricas"""
        import psutil

        metrics = {
            "type": "metrics",
            "cpu_usage": psutil.cpu_percent(),
            "memory_usage": psutil.virtual_memory().percent,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        await manager.send_personal_message(json.dumps(metrics), websocket)

    @staticmethod
    async def handle_heartbeat(websocket: WebSocket):
        """Manejar heartbeat"""
        await manager.send_personal_message(
            json.dumps({"type": "heartbeat", "timestamp": datetime.now(tz=UTC).isoformat()}),
            websocket,
        )


if __name__ == "__main__":
    # Test connection manager
    async def test_websocket():
        # Simular conexión
        manager.connect(None, "test_client")
        print(f"Conexiones activas: {manager.get_connection_count()}")

        # Broadcast
        await manager.broadcast_json({"type": "test", "message": "Hola"})

        # Disconnect
        manager.disconnect(None)
        print(f"Conexiones activas: {manager.get_connection_count()}")

    asyncio.run(test_websocket())
