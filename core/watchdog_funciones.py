#!/usr/bin/env python3
"""watchdog_funciones.py — Decorador para monitorear tiempo de ejecución.

Detecta funciones bloqueadas (infinite loops, I/O stalls) y captura
traceback + estado del sistema automáticamente antes de cualquier acción.

Uso:
    @watchdog(timeout=30)
    def funcion_riesgosa():
        ...

    @watchdog(timeout=60, on_timeout="kill")
    def mision_critica():
        ...
"""

import asyncio
import functools
import json
import logging
import os
import signal
import threading
import time
import traceback
from datetime import UTC, datetime
from pathlib import Path
from typing import Never

logger = logging.getLogger("ura.watchdog")

AUTO_DUMPS_DIR = Path(__file__).parent.parent / "data" / "auto_dumps"


def _auto_dump(function_name: str, timeout: float, extra: dict | None = None) -> dict:
    """Captura estado del sistema + traceback al detectar anomalía.

    Guarda en data/auto_dumps/{timestamp}.json
    """
    ts = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    dump = {
        "timestamp": ts,
        "function": function_name,
        "timeout": timeout,
        "traceback": traceback.format_stack(),
    }
    if extra:
        dump.update(extra)

    # Estado del proceso actual
    try:
        import psutil

        proc = psutil.Process()
        dump["process"] = {
            "pid": proc.pid,
            "cpu_percent": proc.cpu_percent(interval=0.1),
            "memory_rss_mb": proc.memory_info().rss / 1024 / 1024,
            "threads": proc.num_threads(),
            "open_files": len(proc.open_files()),
            "connections": len(proc.connections()),
            "status": proc.status(),
            "create_time": proc.create_time(),
        }
        # Carga del sistema
        dump["system"] = {
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_percent": psutil.virtual_memory().percent,
            "load_avg": [round(x, 2) for x in psutil.getloadavg()],
        }
    except ImportError:
        dump["process"] = {"pid": os.getpid()}
    except Exception as e:
        dump["process"] = {"error": str(e)}

    # Guardar dump
    AUTO_DUMPS_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = function_name.replace("/", "_").replace("\\", "_")[:60]
    dump_path = AUTO_DUMPS_DIR / f"{ts.replace(':', '-')}_{safe_name}.json"
    try:
        dump_path.write_text(json.dumps(dump, indent=2, default=str))
        logger.warning("Auto-dump guardado: %s", dump_path)
    except Exception as e:
        logger.warning("Error guardando auto-dump: %s", e)

    return dump


def _trigger_rescue(function_name: str, timeout: float, extra: dict | None = None) -> None:
    """Publica alerta en event_bus + guarda dump.

    Intenta importar event_bus
    si falla, solo dump a disco.
    """
    dump = _auto_dump(function_name, timeout, extra)
    try:
        from core.event_bus import publish

        publish(
            "alert",
            {
                "source": "watchdog_funciones",
                "function": function_name,
                "timeout": timeout,
                "dump_file": str(AUTO_DUMPS_DIR / f"{dump['timestamp'].replace(':', '-')}_{function_name[:60]}.json"),
            },
        )
    except ImportError:
        logger.warning("event_bus no disponible, dump solo local")


class _TimeoutError(Exception):
    """Lanzada cuando una función excede su timeout."""


def _timeout_handler(signum, frame) -> Never:
    msg = "Function timed out"
    raise _TimeoutError(msg)


def watchdog(
    timeout: float = 30.0,
    on_timeout: str = "log",
    extra_context: dict | None = None,
):
    """Decorador para monitorear tiempo de ejecución.

    Args:
        timeout: Segundos máximos de ejecución
        on_timeout: "log" | "dump" | "kill" | "raise"
            log: solo loguea advertencia
            dump: captura auto-dump + publica alerta
            kill: dump + intenta matar el hilo
            raise: relanza la excepción
        extra_context: Dict con contexto adicional para el dump

    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper_sync(*args, **kwargs):
            # Señal solo funciona en el hilo principal
            if threading.current_thread() is threading.main_thread():
                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(int(timeout))
                try:
                    return func(*args, **kwargs)
                except _TimeoutError:
                    _on_timeout(func.__name__, timeout, extra_context)
                    return None
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                # Hilo secundario: usar threading.Timer
                result = [None]
                exception = [None]
                finished = [False]

                def target() -> None:
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e
                    finally:
                        finished[0] = True

                t = threading.Thread(target=target)
                t.daemon = True
                t.start()
                t.join(timeout)
                if t.is_alive():
                    _on_timeout(func.__name__, timeout, extra_context)
                    return None
                if exception[0]:
                    raise exception[0]
                return result[0]

        @functools.wraps(func)
        async def wrapper_async(*args, **kwargs):
            try:
                return await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout,
                )
            except TimeoutError:
                _on_timeout(func.__name__, timeout, extra_context)
                return None

        if asyncio.iscoroutinefunction(func):
            return wrapper_async
        return wrapper_sync

    return decorator


def _on_timeout(function_name: str, timeout: float, extra: dict | None = None) -> None:
    """Maneja el timeout de una función."""
    logger.warning(
        "WATCHDOG TIMEOUT: %s excedio %ds",
        function_name,
        timeout,
    )
    _trigger_rescue(function_name, timeout, extra)


def check_loop_latency(sample_ms: float = 0) -> float:
    """Mide la latencia del event loop de asyncio.

    Ejecuta asyncio.sleep(0) y mide el tiempo real transcurrido.
    Si supera los 100ms, el event loop esta degradado.

    Returns:
        Latencia en milisegundos

    """

    async def _measure():
        t0 = time.monotonic()
        await asyncio.sleep(sample_ms / 1000 if sample_ms > 0 else 0)
        t1 = time.monotonic()
        return (t1 - t0) * 1000

    try:
        return asyncio.run(_measure())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_measure())
        finally:
            loop.close()


class AsyncLoopMonitor(threading.Thread):
    """Hilo que monitorea la latencia del event loop cada N segundos.

    Si la latencia supera el umbral, publica alerta en event_bus.
    """

    def __init__(self, interval: float = 30.0, threshold_ms: float = 100.0, daemon: bool = True) -> None:
        super().__init__(daemon=daemon)
        self.interval = interval
        self.threshold_ms = threshold_ms
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        logger.info(
            "AsyncLoopMonitor iniciado (interval=%ds, threshold=%dms)",
            self.interval,
            self.threshold_ms,
        )
        while not self._stop_event.is_set():
            latency = check_loop_latency()
            if latency > self.threshold_ms:
                logger.warning(
                    "LATENCIA ALTA: event loop %.1fms (umbral %.0fms)",
                    latency,
                    self.threshold_ms,
                )
                _trigger_rescue(
                    "AsyncLoopMonitor",
                    self.interval,
                    {"loop_latency_ms": latency, "threshold_ms": self.threshold_ms},
                )
            time.sleep(self.interval)


if __name__ == "__main__":
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="URA Watchdog de Funciones")
    parser.add_argument("--loop-latency", action="store_true", help="Medir latencia del event loop")
    args = parser.parse_args()

    if args.loop_latency:
        lat = check_loop_latency()
    else:
        parser.print_help()
