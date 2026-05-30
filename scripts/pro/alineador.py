#!/usr/bin/env python3
"""alineador.py — Valida que las respuestas de URA/OpenClaw sean utiles y no se desvien.
Se ejecuta en la tuneladora para auditar el comportamiento."""

import json
from datetime import datetime
from pathlib import Path

LOG = Path.home() / "URA/ura_ia_1972/logs/alineador.log"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
MONOLOGO = Path("/opt/ura/data/monologo_interno.json")
LOG.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    with open(LOG, "a") as f:
        f.write(f"{datetime.now().isoformat()} - {msg}\n")
    print(msg)


def check_monologo():
    """Verifica que el monologo tenga acciones reales, no charla."""
    if not MONOLOGO.exists():
        log("⚠️ Monologo interno no encontrado")
        return False

    with open(MONOLOGO) as f:
        acciones = json.load(f)

    if not acciones:
        log("⚠️ Monologo vacio — URA no ha ejecutado acciones")
        return False

    ultimas = acciones[-10:]
    ok_count = sum(1 for a in ultimas if a.get("ok", False))
    total = len(ultimas)

    log(f"Ultimas {total} acciones: {ok_count} exitosas")

    if ok_count == 0 and total > 0:
        log("🔴 Ninguna accion exitosa — revisar tools/MCP")
        agregar_sugerencia(
            "Master Conciencia: 0 acciones exitosas", "Revisar servidor MCP y tools de Open WebUI"
        )
        return False

    if ok_count < total * 0.5:
        log("🟡 Menos del 50% de acciones exitosas")
        return False

    log("🟢 Tasa de exito aceptable")
    return True


def check_deviation(message):
    """Detecta si un mensaje se desvia del objetivo (contiene filosofia, opiniones, etc)."""
    deviation_markers = [
        "desde mi perspectiva",
        "en mi opinion",
        "como IA",
        "como asistente",
        "es importante considerar",
        "hay que tener en cuenta",
        "deberias",
        "te recomiendo que",
        "podriamos",
        "tal vez",
        "quizas",
    ]
    return any(marker in message.lower() for marker in deviation_markers)


def agregar_sugerencia(problema, solucion):
    sugerencias = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:
            sugerencias = json.load(f)
    sugerencias.append(
        {
            "timestamp": datetime.now().timestamp(),
            "dominio": "alineador",
            "problema": problema,
            "solucion": solucion,
        }
    )
    with open(SUGERENCIAS, "w") as f:
        json.dump(sugerencias, f, indent=2)


def main():
    log("=== Alineador de conciencia ===")
    check_monologo()
    log("=== Alineacion completada ===")


if __name__ == "__main__":
    main()
