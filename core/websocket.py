#!/usr/bin/env python3
"""
URA WebSocket Support - Soporte para WebSockets
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger

logger = get_logger("websocket", log_dir="./logs")


class WebSocketConnection:
    """Conexión WebSocket"""

    def __init__(self, connection_id: str, user_id: str = None):
        """
        Inicializar conexión

        Args:
            connection_id: ID de la conexión
            user_id: ID del usuario
        """
        self.connection_id = connection_id
        self.user_id = user_id
        self.connected_at = datetime.now(tz=UTC)
        self.last_ping = datetime.now(tz=UTC)
        self.subscriptions: set[str] = set()

    def subscribe(self, channel: str) -> None:
        """Suscribir a canal"""
        self.subscriptions.add(channel)
        logger.debug(f"Connection {self.connection_id} subscribed to {channel}")

    def unsubscribe(self, channel: str) -> None:
        """Desuscribir de canal"""
        self.subscriptions.discard(channel)
        logger.debug(f"Connection {self.connection_id} unsubscribed from {channel}")

    def is_subscribed(self, channel: str) -> bool:
        """Verificar si está suscrito"""
        return channel in self.subscriptions


class WebSocketManager:
    """Gestor de WebSockets"""

    def __init__(self):
        """Inicializar gestor"""
        self.connections: dict[str, WebSocketConnection] = {}
        self.channels: dict[str, set[str]] = {}  # channel -> connection_ids

    def connect(self, connection_id: str, user_id: str = None) -> WebSocketConnection:
        """
        Conectar cliente

        Args:
            connection_id: ID de la conexión
            user_id: ID del usuario

        Returns:
            Conexión creada
        """
        connection = WebSocketConnection(connection_id, user_id)
        self.connections[connection_id] = connection
        logger.info(f"WebSocket connected: {connection_id}")
        return connection

    def disconnect(self, connection_id: str) -> bool:
        """
        Desconectar cliente

        Args:
            connection_id: ID de la conexión
        """
        if connection_id in self.connections:
            connection = self.connections[connection_id]

            # Remover de canales
            for channel in connection.subscriptions:
                if channel in self.channels and connection_id in self.channels[channel]:
                    self.channels[channel].remove(connection_id)

            del self.connections[connection_id]
            logger.info(f"WebSocket disconnected: {connection_id}")
            return True
        return False

    def subscribe(self, connection_id: str, channel: str) -> bool:
        """
        Suscribir conexión a canal

        Args:
            connection_id: ID de la conexión
            channel: Canal
        """
        if connection_id not in self.connections:
            return False

        self.connections[connection_id].subscribe(channel)

        if channel not in self.channels:
            self.channels[channel] = set()
        self.channels[channel].add(connection_id)

        return True

    def unsubscribe(self, connection_id: str, channel: str) -> bool:
        """
        Desuscribir conexión de canal

        Args:
            connection_id: ID de la conexión
            channel: Canal
        """
        if connection_id not in self.connections:
            return False

        self.connections[connection_id].unsubscribe(channel)

        if channel in self.channels and connection_id in self.channels[channel]:
            self.channels[channel].remove(connection_id)

        return True

    def broadcast(self, channel: str, message: dict[str, Any]) -> int:
        """
        Enviar mensaje a todos los suscritos a un canal

        Args:
            channel: Canal
            message: Mensaje

        Returns:
            Número de conexiones que recibieron el mensaje
        """
        if channel not in self.channels:
            return 0

        connection_ids = self.channels[channel].copy()
        count = 0

        for conn_id in connection_ids:
            if conn_id in self.connections:
                # Enviar mensaje (simulado)
                logger.debug(f"Message sent to {conn_id}: {message}")
                count += 1

        logger.info(f"Broadcast to {count} connections on channel {channel}")
        return count

    def send_to_user(self, user_id: str, message: dict[str, Any]) -> int:
        """
        Enviar mensaje a usuario específico

        Args:
            user_id: ID del usuario
            message: Mensaje

        Returns:
            Número de conexiones que recibieron el mensaje
        """
        count = 0
        for connection in self.connections.values():
            if connection.user_id == user_id:
                # Enviar mensaje (simulado)
                logger.debug(f"Message sent to user {user_id}: {message}")
                count += 1

        return count

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_connections": len(self.connections),
            "total_channels": len(self.channels),
            "channel_subscriptions": {ch: len(conns) for ch, conns in self.channels.items()},
        }


# Instancia global
websocket_manager = WebSocketManager()


if __name__ == "__main__":
    # Test WebSocket manager
    wsm = WebSocketManager()

    # Conectar clientes
    wsm.connect("conn1", "user1")
    wsm.connect("conn2", "user2")

    # Suscribir
    wsm.subscribe("conn1", "chat")
    wsm.subscribe("conn2", "chat")

    # Broadcast
    wsm.broadcast("chat", {"message": "Hello"})

    # Stats
    stats = wsm.get_stats()
    print(f"Stats: {stats}")
