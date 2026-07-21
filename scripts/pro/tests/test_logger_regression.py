#!/usr/bin/env python3
"""Test de regresión: Logger.warn() vs Logger.warning().

Solo verifica archivos que usan el Logger personalizado de tuneladora/.
No verifica logging estándar (que sí tiene .warning()).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

# Archivos que usan Logger personalizado (tienen .warn() como método)
# Solo estos deben usar .warn() y nunca .warning()
LOGGER_FILES = [
    "scripts/pro/tuneladora/engine.py",
    "scripts/pro/tuneladora/logger.py",
    "scripts/pro/tuneladora_mantenimiento.py",
    "scripts/pro/tuneladora_mejora.py",
    "scripts/pro/pipeline_refactor.py",
    "scripts/pro/consolidacion.py",
    "scripts/pro/autonomy/autonomy.py",
    "scripts/pro/autonomy/planner.py",
    "scripts/pro/autonomy/evaluator.py",
    "scripts/pro/autonomy/learning.py",
    "scripts/pro/autonomy/learning/aprendizaje.py",
    "scripts/pro/autonomy/swarm/swarm.py",
    "scripts/pro/autonomy/swarm/coordinator.py",
    "scripts/pro/autonomy/swarm/agents/*.py",
    "scripts/pro/dashboard.py",
]


def main() -> int:
    errors = []

    for pattern in LOGGER_FILES:
        for pyfile in sorted(ROOT.glob(pattern)):
            content = pyfile.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(content.split("\n"), 1):
                # Buscar .warning( pero no logging.warning( (stdlib)
                if ".warning(" in line and "logging.warning" not in line:
                    # Verificar que no sea un comentario
                    stripped = line.strip()
                    if not stripped.startswith("#") and not stripped.startswith("//"):
                        errors.append(f"  {pyfile.relative_to(ROOT)}:{i}: {stripped[:80]}")

    if errors:
        print(f"❌ {len(errors)} archivos usan .warning() en lugar de .warn():")
        for e in errors:
            print(e)
        return 1

    print("✅ Todos los archivos usan warn() correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
