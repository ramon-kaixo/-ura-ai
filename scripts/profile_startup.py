#!/usr/bin/env python3
"""Profile Startup — Diagnóstico de rendimiento de arranque.

Mide el tiempo que tarda cada componente en cargar para identificar cuellos de botella.
"""

import sys
import time
from pathlib import Path

# Añadir proyecto al path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def time_operation(name: str, func) -> float:
    """Ejecuta una función y mide su tiempo."""
    start = time.perf_counter()
    try:
        result = func()
        elapsed = time.perf_counter() - start
        print(f"✓ {name}: {elapsed:.3f}s")
        return elapsed
    except Exception as e:
        elapsed = time.perf_counter() - start
        print(f"✗ {name}: {elapsed:.3f}s (ERROR: {e})")
        return elapsed


def main():
    print("=" * 60)
    print("PROFILE STARTUP — Diagnóstico de rendimiento")
    print("=" * 60)
    print()

    total_start = time.perf_counter()
    times = {}

    # 1. Carga de configuración
    print("[1/5] Cargando configuración...")
    times["config"] = time_operation(
        "core.config_manager",
        lambda: __import__("core.config_manager"),
    )

    # 2. Carga de Model Router
    print("\n[2/5] Cargando Model Router...")
    times["model_router"] = time_operation(
        "core.model_router",
        lambda: __import__("core.model_router"),
    )

    # 3. Carga de Memory Engine
    print("\n[3/5] Cargando Memory Engine...")
    times["memory_engine"] = time_operation(
        "core.memory_engine",
        lambda: __import__("core.memory_engine"),
    )

    # 4. Carga de agentes
    print("\n[4/5] Cargando agentes...")
    times["agents"] = time_operation(
        "agents.agente_sandbox_codigo",
        lambda: __import__("agents.agente_sandbox_codigo"),
    )

    # 5. Verificación de Ollama
    print("\n[5/5] Verificando Ollama...")
    def check_ollama():
        import requests
        try:
            r = requests.get("http://10.164.1.99:11434/api/tags", timeout=2)
            return r.status_code == 200
        except Exception:
            return False

    times["ollama"] = time_operation(
        "Ollama health check",
        check_ollama,
    )

    total_elapsed = time.perf_counter() - total_start

    print()
    print("=" * 60)
    print("RESUMEN")
    print("=" * 60)
    for name, elapsed in times.items():
        print(f"  {name:20s}: {elapsed:.3f}s")
    print(f"  {'TOTAL':20s}: {total_elapsed:.3f}s")
    print()

    # Identificar cuellos de botella
    threshold = 1.0  # 1 segundo
    bottlenecks = [(name, elapsed) for name, elapsed in times.items() if elapsed > threshold]
    if bottlenecks:
        print("⚠️  CUELLOS DE BOTELLA (>1s):")
        for name, elapsed in bottlenecks:
            print(f"  - {name}: {elapsed:.3f}s")
    else:
        print("✓ No se detectaron cuellos de botella significativos")

    return 0


if __name__ == "__main__":
    sys.exit(main())
