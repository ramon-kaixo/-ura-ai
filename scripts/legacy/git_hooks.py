#!/usr/bin/env python3
"""
Git Hooks para CI/CD Automático - URA App
Pre-commit y pre-push hooks
"""

import subprocess
import sys


def pre_commit_hook():
    """Hook pre-commit: ejecutar tests antes de commit"""
    print("Ejecutando tests pre-commit...")

    # Ejecutar tests
    result = subprocess.run(
        ["python3", "-m", "pytest", "tests/", "-v"], capture_output=True, text=True
    )

    if result.returncode != 0:
        print("❌ Tests fallaron - Commit rechazado")
        print(result.stdout)
        return False

    print("✅ Tests pasaron - Commit permitido")
    return True


def pre_push_hook():
    """Hook pre-push: ejecutar sandbox testing antes de push"""
    print("Ejecutando sandbox testing pre-push...")

    # Enviar a sandbox para testing
    from scripts.cascade_sandbox_bridge import cascade_sandbox_bridge

    # Probar cambios principales
    resultado = cascade_sandbox_bridge.obtener_estado_cambios()

    if resultado["rechazados"]:
        print("❌ Hay cambios rechazados por sandbox - Push rechazado")
        return False

    print("✅ Sandbox testing OK - Push permitido")
    return True


if __name__ == "__main__":
    hook_type = sys.argv[1] if len(sys.argv) > 1 else "pre-commit"

    if hook_type == "pre-commit":
        exit(0 if pre_commit_hook() else 1)
    elif hook_type == "pre-push":
        exit(0 if pre_push_hook() else 1)
