#!/usr/bin/env python3
"""event_bus.py — Bus de eventos asíncrono con journal persistente y ZeroMQ PUB/SUB.

Migración completa a asyncio.Lock para evitar deadlocks del event-loop.
Expone API sync compatible con callers existentes vía puente ThreadPoolExecutor.
"""

import asyncio
import json
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import zmq

log = logging.getLogger("event_bus")

IPC_PUB = "ipc:///tmp/ura-events.pub"
TOPIC_ANALYTICS = "analytics"
TOPIC_ALERT = "alert"
TOPIC_COMMAND = "command"
EVENTS_DIR = Path(__file__).parent.parent / "data" / "events"

_pub_sock: Any = None
_pub_lock = asyncio.Lock()
_zmq_ctx: Any = None
_suscriptores: dict[str, list[Callable]] = {}


def _run_async(coro):
    """Puente sync→async: ejecuta una corrutina desde contexto síncrono sin bloquear el event-loop."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    with ThreadPoolExecutor(max_workers=1) as executor:
        future = executor.submit(asyncio.run, coro)
        return future.result()


def _journal_path() -> Path:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    return EVENTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"


def _write_journal(topic: str, data: dict) -> None:
    try:
        entry = {
            "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "topic": topic,
            "data": data,
        }
        with open(_journal_path(), "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e:
        log.debug("journal: %s", e)


def replay_events(date: str | None = None, topic: str | None = None) -> list[dict]:
    if date is None:
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = EVENTS_DIR / f"{date}.jsonl"
    if not p.exists():
        return []
    events = []
    try:
        for line in p.read_text().strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
                if topic and e.get("topic") != topic:
                    continue
                events.append(e)
            except json.JSONDecodeError:
                continue
    except Exception as e:
        log.warning("replay: %s", e)
    return events


def _get_ctx() -> Any:
    global _zmq_ctx
    if _zmq_ctx is None:
        _zmq_ctx = zmq.Context()
    return _zmq_ctx


def ensure_publisher() -> None:
    global _pub_sock
    if _pub_sock is not None:
        return
    _run_async(_ensure_publisher_async())


async def _ensure_publisher_async() -> None:
    global _pub_sock
    async with _pub_lock:
        if _pub_sock is not None:
            return
        _pub_sock = _get_ctx().socket(zmq.PUB)
        _pub_sock.bind(IPC_PUB)
        os.chmod(IPC_PUB.replace("ipc://", ""), 0o700)
        log.info("event_bus: PUB en %s", IPC_PUB)


def publish(topic: str, data: dict) -> None:
    ensure_publisher()
    try:
        _write_journal(topic, data)
        if topic == TOPIC_ALERT:
            _trigger_auto_dump(data)
        payload = json.dumps(data, ensure_ascii=False)
        _run_async(_publish_async(topic, payload))
        log.debug("event_bus: publicado %s", topic)
    except Exception as e:
        log.warning("event_bus: error %s: %s", topic, e)


async def _publish_async(topic: str, payload: str) -> None:
    async with _pub_lock:
        _pub_sock.send_multipart([topic.encode(), payload.encode()])


def _trigger_auto_dump(data: dict) -> None:
    try:
        from core.watchdog_funciones import _auto_dump
        func = data.get("function", data.get("source", "event_bus_alert"))
        timeout = data.get("timeout", 0)
        _auto_dump(func, timeout, {"alert_data": data})
    except Exception as e:
        log.debug("auto_dump reactivo: %s", e)


def create_subscriber(topics: list[str]) -> Any:
    sock = _get_ctx().socket(zmq.SUB)
    sock.connect(IPC_PUB)
    for t in topics:
        sock.setsockopt_string(zmq.SUBSCRIBE, t)
    log.info("event_bus: SUB suscrito a %s", topics)
    return sock


def close() -> None:
    global _pub_sock, _zmq_ctx
    _run_async(_close_async())


async def _close_async() -> None:
    global _pub_sock, _zmq_ctx
    async with _pub_lock:
        if _pub_sock:
            try:
                _pub_sock.close()
            except Exception as e:
                log.debug("close: %s", e)
            _pub_sock = None
    if _zmq_ctx:
        try:
            _zmq_ctx.term()
        except Exception as e:
            log.debug("term: %s", e)
        _zmq_ctx = None
    sock_path = IPC_PUB.replace("ipc://", "")
    if os.path.exists(sock_path):
        try:
            os.unlink(sock_path)
        except Exception:
            pass


# ─── AsyncEventBus — Nueva API async pura para futuros consumidores ───

class AsyncEventBus:
    """Bus de eventos asíncrono con suscripciones y despacho concurrente."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._suscriptores: dict[str, list[Callable]] = {}

    async def suscribir(self, evento_tipo: str, callback: Callable) -> None:
        async with self._lock:
            if evento_tipo not in self._suscriptores:
                self._suscriptores[evento_tipo] = []
            if callback not in self._suscriptores[evento_tipo]:
                self._suscriptores[evento_tipo].append(callback)
                log.debug("AsyncEventBus: suscripción añadida para %s", evento_tipo)

    async def emitir(self, evento_tipo: str, datos: Any) -> None:
        async with self._lock:
            consumidores = list(self._suscriptores.get(evento_tipo, []))
        if not consumidores:
            return
        tareas = [
            asyncio.to_thread(cb, datos) if not asyncio.iscoroutinefunction(cb) else cb(datos)
            for cb in consumidores
        ]
        await asyncio.gather(*tareas, return_exceptions=True)
