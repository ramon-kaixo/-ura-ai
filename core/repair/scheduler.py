#!/usr/bin/env python3
"""
core/repair/scheduler.py - Scheduling functionality for auto-repair
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def schedule_repair(instance, error_type: str, error_message: str, schedule_time: str) -> bool:
    """Programar reparación para horario específico"""
    try:
        schedule_file = Path(__file__).parent.parent.parent / "data" / "scheduled_repairs.json"
        schedule_file.parent.mkdir(parents=True, exist_ok=True)

        # Cargar reparaciones programadas existentes
        scheduled = []
        if schedule_file.exists():
            with open(schedule_file) as f:
                scheduled = json.load(f)

        # Agregar nueva reparación programada
        scheduled.append(
            {
                "error_type": error_type,
                "error_message": error_message,
                "schedule_time": schedule_time,
                "created_at": datetime.now().isoformat(),
                "status": "pending",
            }
        )

        # Guardar
        with open(schedule_file, "w") as f:
            json.dump(scheduled, f, indent=2)

        logger.info(f"Reparación programada para {schedule_time}: {error_type}")
        return True

    except Exception as e:
        logger.error(f"Error programando reparación: {e}")
        return False


def run_scheduled_repairs(instance):
    """Ejecutar reparaciones programadas"""
    try:
        schedule_file = Path(__file__).parent.parent.parent / "data" / "scheduled_repairs.json"

        if not schedule_file.exists():
            return

        with open(schedule_file) as f:
            scheduled = json.load(f)

        current_time = datetime.now()

        for repair in scheduled:
            if repair.get("status") == "pending":
                schedule_time = datetime.fromisoformat(repair["schedule_time"])

                if current_time >= schedule_time:
                    # Ejecutar reparación
                    success, message = instance.attempt_repair(
                        repair["error_type"], repair["error_message"]
                    )

                    repair["status"] = "executed"
                    repair["executed_at"] = datetime.now().isoformat()
                    repair["result"] = {"success": success, "message": message}

                    logger.info(
                        f"Reparación programada ejecutada: {repair['error_type']} - {'Exitosa' if success else 'Fallida'}"
                    )

        # Guardar estado actualizado
        with open(schedule_file, "w") as f:
            json.dump(scheduled, f, indent=2)

    except Exception as e:
        logger.error(f"Error ejecutando reparaciones programadas: {e}")
