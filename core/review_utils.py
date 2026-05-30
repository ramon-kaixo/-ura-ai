#!/usr/bin/env python3
"""
Review Utils - Paso 3A
───────────────────────
Utilidades para revisión semanal y mantenimiento.
"""

import logging
import threading

logger = logging.getLogger(__name__)


def _run_weekly_review(window):
    """Ejecutar revisión semanal de memoria y limpieza."""
    try:
        window.chat_alert("🔄 Iniciando revisión semanal...")

        def _review():
            try:
                # Revisar archivos de memoria
                memory_dir = window.config.get("memory_dir", "memory")
                logger.info(f"Revisando directorio de memoria: {memory_dir}")

                # Simular revisión
                from pathlib import Path

                mem_path = Path(memory_dir)
                if mem_path.exists():
                    files = list(mem_path.glob("*.json"))
                    window.chat_alert(f"📊 Revisión: {len(files)} archivos de memoria encontrados")

                # Revisar logs
                log_dir = Path.home() / ".ura" / "logs"
                if log_dir.exists():
                    log_files = list(log_dir.glob("*.log"))
                    window.chat_alert(f"📋 Revisión: {len(log_files)} archivos de log encontrados")

                window.chat_alert("✅ Revisión semanal completada")

            except Exception as exc:
                logger.warning("Revisión semanal falló: %s", exc)
                window.chat_alert("❌ Error en revisión semanal")

        threading.Thread(target=_review, daemon=True).start()
    except Exception as exc:
        logger.warning("_run_weekly_review falló: %s", exc)
