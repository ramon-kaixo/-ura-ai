#!/usr/bin/env python3
"""
Timeout Manager - Sistema central de timeouts para URA

Proporciona:
- @with_timeout(seconds): decorador para envolver funciones con timeout
- TimeoutManager: registro central de timeouts con alertas
- Integracion con observability y Pushover
"""

import concurrent.futures
import logging
import os
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable, Optional
from core.observability import URALogger

logger = logging.getLogger(__name__)

TIMEOUT_LOG = Path.home() / ".ura" / "timeouts.jsonl"
TIMEOUT_LOG.parent.mkdir(parents=True, exist_ok=True)

PUSHOVER_USER = os.environ.get("PUSHOVER_USER_KEY", "")
PUSHOVER_TOKEN = os.environ.get("PUSHOVER_APP_TOKEN", "")

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=8, thread_name_prefix="timeout_mgr")


class TimeoutManager:
    """Gestor central de timeouts con registro y alertas."""

    _instance: Optional["TimeoutManager"] = None

    def __new__(cls) -> "TimeoutManager":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self.timeout_counts: dict[str, int] = {}
        self.recent_timeouts: list[dict] = []

    def register_timeout(
        self,
        agent_name: str,
        function_name: str,
        timeout_s: float,
        duration_s: float,
    ) -> None:
        """Registrar un timeout ocurrido."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "agent": agent_name,
            "function": function_name,
            "timeout_s": timeout_s,
            "duration_s": duration_s,
        }

        key = f"{agent_name}:{function_name}"
        self.timeout_counts[key] = self.timeout_counts.get(key, 0) + 1
        self.recent_timeouts.append(entry)

        if len(self.recent_timeouts) > 100:
            self.recent_timeouts = self.recent_timeouts[-100:]

        with open(TIMEOUT_LOG, "a") as f:
            import json

            f.write(json.dumps(entry) + "\n")

        logger.warning(
            f"Timeout: {agent_name}.{function_name} "
            f"({duration_s:.1f}s > {timeout_s}s) "
            f"[#{self.timeout_counts[key]}]"
        )

        if self.timeout_counts[key] >= 3:
            self._alert(agent_name, function_name, timeout_s, self.timeout_counts[key])

    def _alert(self, agent_name: str, function_name: str, timeout_s: float, count: int) -> None:
        """Enviar alerta por Pushover si esta configurado."""
        if not (PUSHOVER_USER and PUSHOVER_TOKEN):
            return

        import urllib.request

        msg = f"Timeout repetido ({count}x): {agent_name}.{function_name} excede {timeout_s}s"

        try:
            data = urllib.parse.urlencode(
                {
                    "token": PUSHOVER_TOKEN,
                    "user": PUSHOVER_USER,
                    "title": "URA Timeout Alert",
                    "message": msg,
                    "priority": "1",
                }
            ).encode()
            urllib.request.urlopen(  # nosec B310
                urllib.request.Request("https://api.pushover.net/1/messages.json", data=data),
                timeout=5,
            )
        except Exception as e:
            logger.warning(f"Timeout alert failed: {e}")

    def get_stats(self) -> dict:
        """Obtener estadisticas de timeouts."""
        return {
            "total_timeouts": sum(self.timeout_counts.values()),
            "top_agents": sorted(self.timeout_counts.items(), key=lambda x: x[1], reverse=True)[
                :10
            ],
            "recent": self.recent_timeouts[-20:],
        }


def get_timeout_manager() -> TimeoutManager:
    """Obtener el singleton de TimeoutManager."""
    return TimeoutManager()


def with_timeout(
    timeout_s: float = 30.0,
    agent_name: str | None = None,
    fallback_value: Any = None,
) -> Callable:
    """Decorador que ejecuta una funcion con timeout.

    Si la funcion excede el tiempo, registra el timeout y devuelve fallback_value.

    Uso:
        @with_timeout(30, agent_name="agente_facturas")
        def generar_factura(datos):
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = agent_name or getattr(func, "__module__", "unknown").split(".")[-1]
            t_start = time.time()
            obs_logger = URALogger(name)
            obs_logger.log_inicio({"func": func.__name__})

            try:
                future = _executor.submit(func, *args, **kwargs)
                result = future.result(timeout=timeout_s)
                duration_s = time.time() - t_start
                obs_logger.log_ok(
                    str(result)[:500] if result else "",
                    duracion_ms=int(duration_s * 1000),
                )
                return result
            except concurrent.futures.TimeoutError:
                duration_s = time.time() - t_start
                get_timeout_manager().register_timeout(name, func.__name__, timeout_s, duration_s)
                obs_logger.log_error(f"Timeout {timeout_s}s excedido ({duration_s:.1f}s)")
                logger.error(
                    f"Timeout: {name}.{func.__name__} excedio {timeout_s}s "
                    f"({duration_s:.1f}s reales)"
                )
                return fallback_value
            except Exception as e:
                duration_s = time.time() - t_start
                obs_logger.log_error(str(e)[:200])
                raise

        return wrapper

    return decorator


def with_async_timeout(
    timeout_s: float = 30.0,
    agent_name: str | None = None,
    fallback_value: Any = None,
) -> Callable:
    """Decorador para funciones asincronas con timeout via asyncio.wait_for."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            import asyncio

            name = agent_name or getattr(func, "__module__", "unknown").split(".")[-1]
            t_start = time.time()
            obs_logger = URALogger(name)
            obs_logger.log_inicio({"func": func.__name__})

            try:
                result = await asyncio.wait_for(func(*args, **kwargs), timeout=timeout_s)
                duration_s = time.time() - t_start
                obs_logger.log_ok(
                    str(result)[:500] if result else "",
                    duracion_ms=int(duration_s * 1000),
                )
                return result
            except TimeoutError:
                duration_s = time.time() - t_start
                get_timeout_manager().register_timeout(name, func.__name__, timeout_s, duration_s)
                obs_logger.log_error(f"Timeout {timeout_s}s excedido ({duration_s:.1f}s)")
                logger.error(
                    f"Async timeout: {name}.{func.__name__} excedio {timeout_s}s "
                    f"({duration_s:.1f}s reales)"
                )
                return fallback_value
            except Exception as e:
                duration_s = time.time() - t_start
                obs_logger.log_error(str(e)[:200])
                raise

        return wrapper

    return decorator
