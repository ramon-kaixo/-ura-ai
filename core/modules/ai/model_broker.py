"""Model Broker — Motor de decisión con ZeroMQ event subscription.

Corrutina del ura-supervisor. Recibe eventos vía ZeroMQ PUB/SUB desde
data_analyzer, evalúa reglas (FSM) y emite comandos hacia action_handler.
"""

import asyncio
import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import zmq
import zmq.asyncio

log = logging.getLogger("ai.broker")
DB_PATH = Path(__file__).parent.parent.parent / "data" / "processed" / "analytics.db"
ALERTS_LOG = Path(__file__).parent.parent.parent / "logs" / "infra_actions.log"

_decision_history: deque = deque(maxlen=50)
ALLOWED_ACTIONS = {"turbo", "eco", "auto", "restart_router", "flush_logs", "alert"}
IPC_EVENTS = "ipc:///tmp/ura-events.pub"


def _get_latest_analytics() -> list[dict]:
    import sqlite3
    if not DB_PATH.exists():
        return []
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT source, metric_name, AVG(metric_value) as avg_val, "
            "AVG(moving_avg) as avg_mov FROM analytics GROUP BY source, metric_name"
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.warning("ai.broker: error DB: %s", e)
        return []


async def _event_listener() -> None:
    """Bucle que escucha eventos ZeroMQ y los procesa."""
    ctx = zmq.asyncio.Context()
    sock = ctx.socket(zmq.SUB)
    sock.connect(IPC_EVENTS)
    sock.setsockopt_string(zmq.SUBSCRIBE, "analytics")
    sock.setsockopt_string(zmq.SUBSCRIBE, "alert")
    log.info("ai.broker: escuchando eventos en %s", IPC_EVENTS)

    try:
        while True:
            try:
                topic, payload = await sock.recv_multipart()
                data = json.loads(payload.decode())
                log.debug("ai.broker: evento recibido %s → %s", topic.decode(), data)
                # Evaluar tras recibir evento
                action = await _evaluate(data)
                if action and action in ALLOWED_ACTIONS:
                    from core.modules.infra.action_handler import execute_action
                    await execute_action(action)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                log.debug("ai.broker: error en evento: %s", e)
    finally:
        sock.close()
        ctx.term()


async def _evaluate(event_data: dict | None = None) -> str | None:
    """Evalúa analytics y decide acción. FSM extendida."""
    rows = _get_latest_analytics()
    if not rows:
        return None

    action = None
    for r in rows:
        m = r["metric_name"]
        avg = r["avg_val"]
        if m == "latency_ms" and avg > 5.0:
            action = "eco"
            break

    if action:
        ts = datetime.now(timezone.utc).isoformat()
        _decision_history.append({"action": action, "ts": ts, "reason": f"latency={avg}"})
        ALERTS_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ALERTS_LOG, "a") as f:
            f.write(json.dumps({"ts": ts, "action": action, "reason": f"latency={avg}"}) + "\n")
        log.info("ai.broker: decision → %s", action)

    return action


async def evaluate_and_act(fsm_state: dict | None = None) -> str | None:
    """API pública para tests sincrónicos."""
    return await _evaluate(fsm_state)


async def ai_cycle() -> None:
    """Ciclo principal: lanza el listener de eventos (se ejecuta una vez)."""
    try:
        await _event_listener()
    except Exception as e:
        log.warning("ai.broker: ciclo terminó: %s", e)


def get_broker_status() -> dict:
    return {
        "decisions_in_history": len(_decision_history),
        "allowed_actions": sorted(ALLOWED_ACTIONS),
        "last_actions": list(_decision_history)[-5:] if _decision_history else [],
        "event_bus": IPC_EVENTS,
    }
