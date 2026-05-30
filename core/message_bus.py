import json
import logging
import threading
from typing import Any, Callable

try:
    import redis
except ImportError:
    redis = None

logger = logging.getLogger("MessageBus")


class MessageBus:
    def __init__(self, host: str = "localhost", port: int = 6379) -> None:
        if redis is None:
            raise ImportError("Redis not installed. Run: pip install redis")
        self.client = redis.Redis(host=host, port=port, decode_responses=True)
        self.subscribers: dict[str, list[Callable]] = {}

    def publicar(self, canal: str, mensaje: dict[str, Any]) -> None:
        self.client.publish(canal, json.dumps(mensaje))
        logger.info("Publicado en %s: %s", canal, mensaje)

    def suscribir(self, canal: str, callback: Callable[[dict[str, Any]], None]) -> None:
        def oyente() -> None:
            pubsub = self.client.pubsub()
            pubsub.subscribe(canal)
            for msg in pubsub.listen():
                if msg["type"] == "message":
                    data = json.loads(msg["data"])
                    callback(data)

        thread = threading.Thread(target=oyente, daemon=True)
        thread.start()
        logger.info("Suscrito a %s", canal)
