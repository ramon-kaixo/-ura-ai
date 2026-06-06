"""event_bus.py — Bus de eventos ZeroMQ PUB/SUB entre módulos URA.

Capa de comunicación interna para que data_analyzer publique eventos
y model_broker los reciba sin polling.
"""

import json
import logging
import os
import threading
from typing import Any

import zmq

log = logging.getLogger("event_bus")

IPC_PUB = "ipc:///tmp/ura-events.pub"
TOPIC_ANALYTICS = "analytics"
TOPIC_ALERT = "alert"
TOPIC_COMMAND = "command"

_pub_sock: Any = None
_pub_lock = threading.Lock()
_zmq_ctx: Any = None


def _get_ctx() -> Any:
    global _zmq_ctx
    if _zmq_ctx is None:
        _zmq_ctx = zmq.Context()
    return _zmq_ctx


def ensure_publisher() -> None:
    """Asegura que el socket PUB está creado (llamado por data_analyzer)."""
    global _pub_sock
    if _pub_sock is not None:
        return
    with _pub_lock:
        if _pub_sock is not None:
            return
        ctx = _get_ctx()
        _pub_sock = ctx.socket(zmq.PUB)
        _pub_sock.bind(IPC_PUB)
        import os as _os
        _os.chmod(IPC_PUB.replace('ipc://', ''), 0o700)
        log.info("event_bus: PUB escuchando en %s", IPC_PUB)


def publish(topic: str, data: dict) -> None:
    """Publica un evento en el bus. Hilo-safe."""
    ensure_publisher()
    try:
        payload = json.dumps(data, ensure_ascii=False)
        with _pub_lock:
            _pub_sock.send_multipart([topic.encode(), payload.encode()])
        log.debug("event_bus: publicado %s", topic)
    except Exception as e:
        log.warning("event_bus: error publicando %s: %s", topic, e)


def create_subscriber(topics: list[str]) -> Any:
    """Crea un socket SUB para suscribirse a topics. Retorna el socket."""
    ctx = _get_ctx()
    sock = ctx.socket(zmq.SUB)
    sock.connect(IPC_PUB)
    for topic in topics:
        sock.setsockopt_string(zmq.SUBSCRIBE, topic)
    log.info("event_bus: SUB suscrito a %s", topics)
    return sock


def close() -> None:
    """Limpieza global."""
    global _pub_sock, _zmq_ctx
    with _pub_lock:
        if _pub_sock:
            try:
                _pub_sock.close()
            except Exception as e:
                log.debug("event_bus.close: %s", e)
            _pub_sock = None
    if _zmq_ctx:
        try:
            _zmq_ctx.term()
        except Exception as e:
            log.debug("event_bus.term: %s", e)
        _zmq_ctx = None
    sock_path = IPC_PUB.replace("ipc://", "")
    if os.path.exists(sock_path):
        try:
            os.unlink(sock_path)
        except Exception:
            log.debug("silent exception in %s", e if 'e' in prev else 'event_bus')
