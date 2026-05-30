#!/usr/bin/env python3
"""
Handler Utils - Paso 2A
────────────────────────
Funciones auxiliares para handlers de comandos.
"""

import json
import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)


def get_health_report_from_file() -> str:
    """
    Obtener informe de salud desde integration_test_results.json.

    Returns:
        String con el informe de salud
    """
    benchmarks_dir = Path(__file__).parent.parent / "benchmarks"
    integration_results = benchmarks_dir / "integration_test_results.json"

    try:
        if integration_results.exists():
            with open(integration_results) as f:
                data = json.load(f)

            # Analizar resultados
            all_systems_ok = True
            issues = []

            # Verificar TTFT
            if "Test 1: Sincronización" in data.get("results", {}):
                recovery_time = (
                    data["results"]["Test 1: Sincronización"]
                    .get("Tiempo recuperación", {})
                    .get("value", 0)
                )
                if recovery_time > 10:
                    all_systems_ok = False
                    issues.append(f"Recuperación lenta: {recovery_time}s")

            # Generar informe
            if all_systems_ok:
                return "✅ Todos los sistemas operativos. Tiempo de recuperación: OK"
            else:
                return f"⚠️ Problemas detectados: {', '.join(issues)}"
        else:
            return "⚠️ No hay resultados de tests disponibles"
    except Exception as e:
        logger.error(f"Error leyendo informe de salud: {e}")
        return f"❌ Error al leer informe: {str(e)}"


def format_timestamp() -> str:
    """Generar timestamp actual en formato HH:MM:SS."""
    return time.strftime("%H:%M:%S")


def escape_html(text: str) -> str:
    """Escapar caracteres HTML para visualización segura."""
    return (
        text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br>")
    )
