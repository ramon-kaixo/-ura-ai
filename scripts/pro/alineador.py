#!/usr/bin/env python3
"""alineador.py — Valida que las respuestas de URA/OpenClaw sean utiles y no se desvien.
Combina substring matching + embedding distance via Qdrant.
Se ejecuta en la tuneladora para auditar el comportamiento.
"""

PLUGIN = {
    "name": "alineador",
    "phase": "post",
    "timeout": 30,
    "blocking": False,
    "needs_file": False,
}

import json
import math
from datetime import UTC, datetime
from pathlib import Path

LOG = Path.home() / "URA/ura_ia_1972/logs/alineador.log"
SUGERENCIAS = Path("/opt/ura/data/sugerencias.json")
MONOLOGO = Path("/opt/ura/data/monologo_interno.json")

from motor.core.config import UraConfig
from motor.core.qdrant_client import COLECCION_TRANSACCIONES, QdrantClient

_qdrant = None


def _get_qdrant():
    global _qdrant  # noqa: PLW0603
    if _qdrant is None:
        _qdrant = QdrantClient.instancia(UraConfig.load())
    return _qdrant


def log(msg) -> None:
    with open(LOG, "a") as f:  # noqa: PTH123
        f.write(f"{datetime.now(UTC).isoformat()} - {msg}\n")


def _distancia_coseno(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=False))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(x * x for x in b))
    if not na or not nb:
        return 1.0
    return 1.0 - (dot / (na * nb))


def check_deviation(message: str) -> dict:
    """Detecta si un mensaje se desvia del objetivo.
    Retorna {"deviated": bool, "reasons": list[str], "distance": float}.
    """
    reasons = []
    deviated_substring = False
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
    for marker in deviation_markers:
        if marker in message.lower():
            reasons.append(f"marcador: '{marker}'")
            deviated_substring = True

    # Embedding check via Qdrant (si disponible)
    deviated_embedding = False
    distancia = 0.0
    try:
        qdrant = _get_qdrant()
        if qdrant.disponible:
            query_vec = qdrant.generar_embedding(message)
            similares = qdrant.buscar_por_similitud(query_vec, COLECCION_TRANSACCIONES, limit=5)
            if similares:
                # Distancia promedio vs transacciones conocidas
                distancias = [s["score"] for s in similares if s.get("score") is not None]
                if distancias:
                    # Qdrant devuelve score (1 = identico), convertir a distancia
                    sim_media = sum(distancias) / len(distancias)
                    distancia = 1.0 - sim_media
                    if distancia > 0.5:
                        reasons.append(f"embedding: distancia {distancia:.3f} > 0.5")
                        deviated_embedding = True
    except Exception as e:
        log(f"embedding check falló: {e}")

    deviated = deviated_substring or deviated_embedding
    log(f"Deviation check: deviated={deviated}, substring={deviated_substring}, embedding_dist={distancia:.3f}")
    return {"deviated": deviated, "reasons": reasons, "distance": round(distancia, 4)}


def check_monologo() -> bool:
    if not MONOLOGO.exists():
        log("Monologo interno no encontrado")
        return False

    with open(MONOLOGO) as f:  # noqa: PTH123
        acciones = json.load(f)

    if not acciones:
        log("Monologo vacio — URA no ha ejecutado acciones")
        return False

    ultimas = acciones[-10:]
    ok_count = sum(1 for a in ultimas if a.get("ok", False))
    total = len(ultimas)

    log(f"Ultimas {total} acciones: {ok_count} exitosas")

    if ok_count == 0 and total > 0:
        agregar_sugerencia(
            "Master Conciencia: 0 acciones exitosas",
            "Revisar servidor MCP y tools de Open WebUI",
        )
        return False

    if ok_count < total * 0.5:
        log("Menos del 50% de acciones exitosas")
        return False

    log("Tasa de exito aceptable")
    return True


def agregar_sugerencia(problema, solucion) -> None:
    sugerencias = []
    if SUGERENCIAS.exists():
        with open(SUGERENCIAS) as f:  # noqa: PTH123
            sugerencias = json.load(f)
    sugerencias.append(
        {
            "timestamp": datetime.now(UTC).timestamp(),
            "dominio": "alineador",
            "problema": problema,
            "solucion": solucion,
        },
    )
    with open(SUGERENCIAS, "w") as f:  # noqa: PTH123
        json.dump(sugerencias, f, indent=2)


def scan_project() -> None:
    root = Path.home() / "URA/ura_ia_1972"
    list(root.rglob("*.py"))


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Alineador URA/OpenClaw")
    parser.add_argument("--scan", action="store_true", help="Escanear todo el proyecto")
    parser.add_argument("--message", type=str, help="Verificar desviacion de un mensaje")
    parser.add_argument("--check-all", action="store_true", help="Ejecutar todas las validaciones")
    args = parser.parse_args()

    if args.message:
        result = check_deviation(args.message)
        return

    if args.scan:
        scan_project()
        return

    log("=== Alineador de conciencia ===")
    check_monologo()

    if args.check_all:
        log("=== Verificacion de desviacion en ultimas acciones ===")
        if MONOLOGO.exists():
            with open(MONOLOGO) as f:  # noqa: PTH123
                acciones = json.load(f)
            for accion in acciones[-3:]:
                msg = accion.get("mensaje", accion.get("output", ""))
                if msg:
                    result = check_deviation(msg)
                    if result["deviated"]:
                        log(f"Desviacion detectada: {result['reasons']}")
                        agregar_sugerencia(
                            f"Desviacion en mensaje: {result['reasons'][:1]}",
                            "Revisar prompt principal de URA para eliminar sesgos",
                        )
    log("=== Alineacion completada ===")


if __name__ == "__main__":
    main()
