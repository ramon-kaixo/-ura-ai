#!/usr/bin/env python3
"""
Sistema de tracking de OpenClaw para URA.

URA puede consultar en todo momento el estado de OpenClaw
y ver qué operaciones está realizando.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any
from collections import deque
import threading

logger = __import__("logging").getLogger("openclaw_tracker")

TRACKING_FILE = Path("/Users/ramonesnaola/URA/ura_ia_1972/.openclaw_tracking.json")
MAX_HISTORY = 100


@dataclass
class OpenClawOperation:
    """Representa una operación de OpenClaw."""

    search_id: str
    timestamp: str
    tema: str
    modo: str
    estado: str
    duracion_segundos: float
    resultados_count: int
    error: str | None = None
    modelo: str | None = None
    availability: str | None = None


class OpenClawTracker:
    """Tracker de operaciones de OpenClaw para visibilidad de URA."""

    def __init__(self, tracking_file: Path | None = None):
        self.tracking_file = tracking_file or TRACKING_FILE
        self.history: deque[OpenClawOperation] = deque(maxlen=MAX_HISTORY)
        self.current_operation: OpenClawOperation | None = None
        self.lock = threading.Lock()
        self._load_history()

    def _load_history(self):
        """Carga historial desde archivo."""
        if self.tracking_file.exists():
            try:
                with open(self.tracking_file) as f:
                    data = json.load(f)
                    for op_data in data:
                        self.history.append(OpenClawOperation(**op_data))
                logger.info(f"Cargados {len(self.history)} operaciones del historial")
            except Exception as e:
                logger.warning(f"Error cargando historial: {e}")

    def _save_history(self):
        """Guarda historial a archivo."""
        try:
            with open(self.tracking_file, "w") as f:
                json.dump([asdict(op) for op in self.history], f, indent=2)
        except Exception as e:
            logger.error(f"Error guardando historial: {e}")

    def start_operation(
        self,
        search_id: str,
        tema: str,
        modo: str,
        modelo: str | None = None,
        availability: str | None = None,
    ):
        """Registra inicio de operación OpenClaw."""
        with self.lock:
            self.current_operation = OpenClawOperation(
                search_id=search_id,
                timestamp=datetime.now().isoformat(),
                tema=tema,
                modo=modo,
                estado="in_progress",
                duracion_segundos=0.0,
                resultados_count=0,
                modelo=modelo,
                availability=availability,
            )
            logger.info(f"[TRACKER] Operación iniciada: {search_id} - {tema[:50]}...")
            self._log_to_scribe("openclaw_start", search_id, tema, modo, modelo, availability)

    def complete_operation(
        self,
        search_id: str,
        estado: str,
        duracion: float,
        resultados_count: int,
        error: str | None = None,
    ):
        """Registra completitud de operación OpenClaw."""
        with self.lock:
            if self.current_operation and self.current_operation.search_id == search_id:
                self.current_operation.estado = estado
                self.current_operation.duracion_segundos = duracion
                self.current_operation.resultados_count = resultados_count
                self.current_operation.error = error
                self.history.append(self.current_operation)
                self._save_history()
                self.current_operation = None
                logger.info(
                    f"[TRACKER] Operación completada: {search_id} - estado: {estado}, duración: {duracion}s"
                )
                self._log_to_scribe(
                    "openclaw_complete",
                    search_id,
                    self.current_operation.tema,
                    self.current_operation.modo,
                    self.current_operation.modelo,
                    self.current_operation.availability,
                    estado=estado,
                    duracion=duracion,
                    resultados=resultados_count,
                    error=error,
                )
            else:
                logger.warning(
                    f"[TRACKER] No se encontró operación actual para search_id: {search_id}"
                )

    def _log_to_scribe(
        self,
        event_type: str,
        search_id: str,
        tema: str,
        modo: str,
        modelo: str | None = None,
        availability: str | None = None,
        estado: str | None = None,
        duracion: float = 0,
        resultados: int = 0,
        error: str | None = None,
    ) -> None:
        """Registra la operacion en forensic_scribe para trazabilidad completa."""
        try:
            from core.forensic_scribe import get_forensic_scribe

            scribe = get_forensic_scribe()
            scribe.log_event(
                event_type=event_type,
                module="openclaw_tracker",
                action="openclaw_operation",
                context={
                    "search_id": search_id,
                    "tema": tema[:200] if tema else "",
                    "modo": modo,
                    "modelo": modelo,
                    "availability": availability,
                    "estado": estado,
                    "duracion_segundos": duracion,
                    "resultados_count": resultados,
                    "error": error,
                },
                dependencies=["openclaw"],
            )
        except Exception:
            pass

    def get_current_status(self) -> dict[str, Any]:
        """Retorna estado actual de OpenClaw para URA."""
        with self.lock:
            if self.current_operation:
                return {
                    "status": "busy",
                    "operation": asdict(self.current_operation),
                    "timestamp": datetime.now().isoformat(),
                }
            else:
                return {
                    "status": "idle",
                    "last_operation": asdict(self.history[-1]) if self.history else None,
                    "total_operations": len(self.history),
                    "timestamp": datetime.now().isoformat(),
                }

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Retorna historial de operaciones."""
        with self.lock:
            return [asdict(op) for op in list(self.history)[-limit:]]

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas de operaciones."""
        with self.lock:
            if not self.history:
                return {"total": 0}

            successful = sum(1 for op in self.history if op.estado == "ok")
            errors = sum(1 for op in self.history if op.estado == "error")
            timeouts = sum(1 for op in self.history if "timeout" in (op.error or "").lower())
            avg_duration = sum(op.duracion_segundos for op in self.history) / len(self.history)

            return {
                "total": len(self.history),
                "successful": successful,
                "errors": errors,
                "timeouts": timeouts,
                "avg_duration": round(avg_duration, 2),
                "success_rate": round(successful / len(self.history) * 100, 2),
            }


# Singleton
_tracker_instance: OpenClawTracker | None = None


def get_openclaw_tracker() -> OpenClawTracker:
    """Obtener el singleton del tracker."""
    global _tracker_instance
    if _tracker_instance is None:
        _tracker_instance = OpenClawTracker()
    return _tracker_instance


def track_openclaw_operation(
    search_id: str, tema: str, modo: str, modelo: str | None = None, availability: str | None = None
):
    """Decorador para tracking automático de operaciones."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            tracker = get_openclaw_tracker()
            tracker.start_operation(search_id, tema, modo, modelo, availability)
            try:
                result = await func(*args, **kwargs)
                tracker.complete_operation(
                    search_id,
                    result.get("estado", "unknown"),
                    result.get("duracion_segundos", 0),
                    len(result.get("resultados", [])),
                    result.get("error"),
                )
                return result
            except Exception as e:
                tracker.complete_operation(search_id, "error", 0, 0, str(e))
                raise

        return wrapper

    return decorator


if __name__ == "__main__":
    # Test del tracker
    tracker = get_openclaw_tracker()
    print("Estado actual:", tracker.get_current_status())
    print("Historial:", tracker.get_history())
    print("Estadísticas:", tracker.get_stats())
