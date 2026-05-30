#!/usr/bin/env python3
"""
Training Gatekeeper para N3

Controla cuándo se ejecuta el entrenamiento masivo basándose en:
- Umbral de volumen de semillas (default 500)
- Umbral de tiempo desde último entrenamiento (default 7 días)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger("training_gatekeeper")

# Configuración por defecto
DEFAULT_VOLUME_THRESHOLD = 500
DEFAULT_TIME_THRESHOLD_DAYS = 7

# Paths
TRAINING_STATE_PATH = Path.home() / ".ura" / "training_state.json"


class TrainingGatekeeper:
    """Gatekeeper para entrenamiento N3 masivo."""

    def __init__(
        self,
        volume_threshold: int | None = None,
        time_threshold_days: int | None = None,
    ) -> None:
        """
        Inicializa el gatekeeper.

        Args:
            volume_threshold: Umbral de semillas para activar (lee de env var o default)
            time_threshold_days: Días desde último entrenamiento para activar (lee de env var o default)
        """
        self.volume_threshold = volume_threshold or int(
            os.environ.get("URA_TRAINING_VOLUME_THRESHOLD", str(DEFAULT_VOLUME_THRESHOLD))
        )
        self.time_threshold_days = time_threshold_days or int(
            os.environ.get("URA_TRAINING_TIME_THRESHOLD_DAYS", str(DEFAULT_TIME_THRESHOLD_DAYS))
        )

        # Crear directorio .ura si no existe
        TRAINING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"[GATEKEEPER] Inicializado - umbral volumen: {self.volume_threshold}, "
            f"umbral tiempo: {self.time_threshold_days} días"
        )

    def _read_training_state(self) -> dict[str, Any]:
        """Lee el estado de entrenamiento desde JSON."""
        if not TRAINING_STATE_PATH.exists():
            return {"last_activation": None}

        try:
            with open(TRAINING_STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning(f"[GATEKEEPER] Error leyendo training_state.json: {e}")
            return {"last_activation": None}

    def _write_training_state(self, state: dict[str, Any]) -> None:
        """Escribe el estado de entrenamiento a JSON."""
        try:
            with open(TRAINING_STATE_PATH, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, default=str)
        except OSError as e:
            logger.error(f"[GATEKEEPER] Error escribiendo training_state.json: {e}")

    def pending_seeds_count(self) -> int:
        """Cuenta semillas pendientes en el seed_pipeline."""
        try:
            from core.seed_pipeline import get_seed_pipeline

            pipeline = get_seed_pipeline()
            pending = pipeline.get_pending_seeds()
            return len(pending)
        except ImportError as e:
            logger.error(f"[GATEKEEPER] Error importando seed_pipeline: {e}")
            return 0
        except Exception as e:  # noqa: BLE001
            logger.error(f"[GATEKEEPER] Error obteniendo semillas pendientes: {e}")
            return 0

    def get_pending_seeds(self) -> list:
        """Obtiene lista de semillas pendientes (para compatibilidad con tests)."""
        try:
            from core.seed_pipeline import get_seed_pipeline

            pipeline = get_seed_pipeline()
            return pipeline.get_pending_seeds()
        except ImportError as e:
            logger.error(f"[GATEKEEPER] Error importando seed_pipeline: {e}")
            return []
        except Exception as e:  # noqa: BLE001
            logger.error(f"[GATEKEEPER] Error obteniendo semillas pendientes: {e}")
            return []

    def days_since_last_training(self) -> int:
        """Calcula días desde última activación de entrenamiento."""
        state = self._read_training_state()
        last_training = state.get("last_training") or state.get("last_activation")

        if not last_training:
            # Nunca se ha activado → considerar como infinitos días
            return 9999

        try:
            if isinstance(last_training, str):
                last_dt = datetime.fromisoformat(last_training)
            elif isinstance(last_training, datetime):
                last_dt = last_training
            else:
                return 9999

            delta = datetime.now() - last_dt
            return delta.days
        except (ValueError, TypeError) as e:
            logger.warning(f"[GATEKEEPER] Error parseando fecha última activación: {e}")
            return 9999

    def should_activate(self) -> bool:
        """
        Comprueba si se debe activar el entrenamiento.

        Returns:
            True si se debe activar, False si no.
        """
        pending_seeds = self.pending_seeds_count()
        days_since_last = self.days_since_last_training()

        volume_ok = pending_seeds >= self.volume_threshold
        time_ok = days_since_last >= self.time_threshold_days

        logger.info(
            f"[GATEKEEPER] should_activate - semillas pendientes: {pending_seeds} "
            f"(umbral: {self.volume_threshold}), días desde última: {days_since_last} "
            f"(umbral: {self.time_threshold_days})"
        )
        logger.info(f"[GATEKEEPER] Condición volumen: {volume_ok}, condición tiempo: {time_ok}")

        should = volume_ok or time_ok
        logger.info(f"[GATEKEEPER] Resultado should_activate: {should}")

        return should

    def activate_if_ready(self) -> dict[str, Any]:
        """
        Activa el entrenamiento si se cumplen las condiciones.

        Returns:
            Dict con {'activated': bool, 'reason': str, 'queries': int, 'duration': float, 'error': str | None}
        """
        if not self.should_activate():
            pending_seeds = self.pending_seeds_count()
            days_since_last = self.days_since_last_training()
            reason = f"Condiciones no cumplidas ({pending_seeds} semillas, {days_since_last} días desde último entrenamiento)"
            logger.info(f"[GATEKEEPER] {reason}")
            return {
                "activated": False,
                "reason": reason,
                "queries": 0,
                "duration": 0,
                "error": None,
            }

        logger.info("[GATEKEEPER] Condiciones cumplidas. Activando entrenamiento...")

        try:
            import asyncio
            from core.training_orchestrator import TrainingOrchestrator

            orchestrator = TrainingOrchestrator()

            # Ejecutar night_training de forma asíncrona
            loop = asyncio.get_event_loop()
            start_time = datetime.now()
            loop.run_until_complete(orchestrator.night_training(max_queries=100))
            duration = (datetime.now() - start_time).total_seconds()

            # Actualizar estado
            state = {
                "last_training": datetime.now().isoformat(),
                "queries_executed": orchestrator.stats.get("total_queries", 0),
            }
            self._write_training_state(state)

            logger.info("[GATEKEEPER] Entrenamiento completado exitosamente.")
            return {
                "activated": True,
                "reason": "Condiciones cumplidas",
                "queries": state["queries_executed"],
                "duration": duration,
                "error": None,
            }

        except ImportError as e:
            error_msg = f"Error importando training_orchestrator: {e}"
            logger.error(f"[GATEKEEPER] {error_msg}")
            return {
                "activated": False,
                "reason": error_msg,
                "queries": 0,
                "duration": 0,
                "error": error_msg,
            }
        except Exception as e:  # noqa: BLE001
            error_msg = f"Error en entrenamiento: {e}"
            logger.error(f"[GATEKEEPER] {error_msg}", exc_info=True)
            return {
                "activated": False,
                "reason": error_msg,
                "queries": 0,
                "duration": 0,
                "error": error_msg,
            }

    def get_status(self) -> dict[str, Any]:
        """
        Obtiene estado actual del gatekeeper.

        Returns:
            Dict con pending_seeds, days_since_last, threshold_volume, threshold_time, will_activate_on_next_check
        """
        pending_seeds = self.pending_seeds_count()
        days_since_last = self.days_since_last_training()
        will_activate = self.should_activate()

        return {
            "pending_seeds": pending_seeds,
            "days_since_last": days_since_last,
            "threshold_volume": self.volume_threshold,
            "threshold_time": self.time_threshold_days,
            "will_activate_on_next_check": will_activate,
        }


if __name__ == "__main__":
    # Test simple
    logging.basicConfig(level=logging.INFO)
    gatekeeper = TrainingGatekeeper()
    print(f"should_activate: {gatekeeper.should_activate()}")
