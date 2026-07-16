#!/usr/bin/env python3
"""patch_timestamps.py — Corrección de timestamps naive → UTC-aware.

Sustituye datetime.now(UTC).isoformat() por datetime.now(UTC).isoformat()
en todos los archivos objetivo, asegurando consistencia temporal ISO 8601
con zona horaria UTC explícita en todo el ecosistema URA.

Uso: python3 scripts/pro/patch_timestamps.py
"""

from pathlib import Path

archivos_objetivo = [
    "core/memory_engine.py",
    "core/change_guardian.py",
    "core/infra/state_manager.py",
    "core/error_sandbox.py",
    "core/sandbox_orchestrator.py",
    "core/ura_multi_agent.py",
    "scripts/pro/tuneladora_mejora.py",
    "scripts/pro/tuneladora_mantenimiento.py",
    "motor/core/qdrant_client.py",
]


def aplicar_parche_utc() -> None:
    for rel_path in archivos_objetivo:
        abs_path = Path("/home/ramon/URA/ura_ia_1972") / rel_path
        if not abs_path.exists():
            continue

        contenido = abs_path.read_text()

        if "datetime.now(UTC).isoformat()" not in contenido:
            continue

        # Asegurar importación de UTC
        if "from datetime import UTC, datetime, UTC" not in contenido and "from datetime import" in contenido:
            contenido = contenido.replace(
                "from datetime import UTC, datetime",
                "from datetime import UTC, datetime, UTC",
            )
        elif "from datetime import" not in contenido:
            contenido = "from datetime import UTC, datetime, UTC\n" + contenido

        contenido = contenido.replace(
            "datetime.now(UTC).isoformat()",
            "datetime.now(UTC).isoformat()",
        )

        abs_path.write_text(contenido)


if __name__ == "__main__":
    aplicar_parche_utc()
