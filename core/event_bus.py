#!/usr/bin/env python3
"""event_bus.py — Bus de eventos ZeroMQ PUB/SUB con journal persistente."""
import json, logging, os, threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import zmq
log = logging.getLogger("event_bus")
IPC_PUB = "ipc:///tmp/ura-events.pub"
TOPIC_ANALYTICS = "analytics"
TOPIC_ALERT = "alert"
TOPIC_COMMAND = "command"
EVENTS_DIR = Path(__file__).parent.parent / "data" / "events"
_pub_sock: Any = None; _pub_lock = threading.Lock(); _zmq_ctx: Any = None

def _journal_path() -> Path:
    EVENTS_DIR.mkdir(parents=True, exist_ok=True)
    return EVENTS_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"

def _write_journal(topic: str, data: dict) -> None:
    try:
        entry = {"ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ"), "topic": topic, "data": data}
        with open(_journal_path(), "a") as f: f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception as e: log.debug("journal: %s", e)

def replay_events(date: str | None = None, topic: str | None = None) -> list[dict]:
    if date is None: date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    p = EVENTS_DIR / f"{date}.jsonl"
    if not p.exists(): return []
    events = []
    try:
        for line in p.read_text().strip().split("\n"):
            line = line.strip()
            if not line: continue
            try:
                e = json.loads(line)
                if topic and e.get("topic") != topic: continue
                events.append(e)
            except json.JSONDecodeError: continue
    except Exception as e: log.warning("replay: %s", e)
    return events

def _get_ctx() -> Any:
    global _zmq_ctx
    if _zmq_ctx is None: _zmq_ctx = zmq.Context()
    return _zmq_ctx

def ensure_publisher() -> None:
    global _pub_sock
    if _pub_sock is not None: return
    with _pub_lock:
        if _pub_sock is not None: return
        _pub_sock = _get_ctx().socket(zmq.PUB)
        _pub_sock.bind(IPC_PUB)
        import os as _os; _os.chmod(IPC_PUB.replace("ipc://", ""), 0o700)
        log.info("event_bus: PUB en %s", IPC_PUB)

def publish(topic: str, data: dict) -> None:
    ensure_publisher()
    try:
        _write_journal(topic, data)
        payload = json.dumps(data, ensure_ascii=False)
        with _pub_lock: _pub_sock.send_multipart([topic.encode(), payload.encode()])
        log.debug("event_bus: publicado %s", topic)
    except Exception as e: log.warning("event_bus: error %s: %s", topic, e)

def create_subscriber(topics: list[str]) -> Any:
    sock = _get_ctx().socket(zmq.SUB); sock.connect(IPC_PUB)
    for t in topics: sock.setsockopt_string(zmq.SUBSCRIBE, t)
    log.info("event_bus: SUB suscrito a %s", topics); return sock

def close() -> None:
    global _pub_sock, _zmq_ctx
    with _pub_lock:
        if _pub_sock:
            try: _pub_sock.close()
            except Exception as e: log.debug("close: %s", e)
            _pub_sock = None
    if _zmq_ctx:
        try: _zmq_ctx.term()
        except Exception as e: log.debug("term: %s", e)
        _zmq_ctx = None
    sock_path = IPC_PUB.replace("ipc://", "")
    if os.path.exists(sock_path):
        try: os.unlink(sock_path)
        except Exception: pass
