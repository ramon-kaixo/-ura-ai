#!/usr/bin/env python3

import argparse
import subprocess
import sys
import time
from pathlib import Path


def run_command(cmd: list[str], timeout: int = 120) -> bool:
    """Ejecuta un comando con timeout y devuelve True si se completa exitosamente."""
    try:
        print(f"Ejecutando: {' '.join(cmd)}")
        if "--dry-run" in sys.argv:
            return True
        result = subprocess.run(
            cmd,
            cwd=Path(__file__).resolve().parent,
            timeout=timeout,
            check=True,
            capture_output=True,
            text=True,
        )
        print(result.stdout)
        return True
    except subprocess.TimeoutExpired:
        print(f"Timeout excedido para el comando: {' '.join(cmd)}")
        return False
    except subprocess.CalledProcessError as e:
        print(f"Error al ejecutar comando: {' '.join(cmd)}")
        print(f"Salida de error: {e.stderr}")
        return False


def phase_0():
    """Fase 0: Lint y type checking."""
    print("Fase 0: Lint y type checking")
    cmd = [sys.executable, "-m", "ruff", "check", "."]
    if not run_command(cmd):
        return False
    cmd = [sys.executable, "-m", "mypy", "--no-incremental", "core", "motor", "shared"]
    return run_command(cmd)


def phase_1():
    """Fase 1: Tests unitarios."""
    print("Fase 1: Tests unitarios")
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short"]
    return run_command(cmd)


def phase_2():
    """Fase 2: Tests funcionales."""
    print("Fase 2: Tests funcionales")
    cmd = [sys.executable, "-m", "pytest", "-q", "--tb=short", "-k", "not slow and not integration"]
    return run_command(cmd)


def phase_3():
    """Fase 3: Tests de integración y contratos (marcadores integrados)."""
    print("Fase 3: Tests de integración y contratos")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-m",
        "integration",
        "--ignore=tests/integration/test_llm_contract.py",
        "--ignore=tests/integration/test_api.py",
    ]
    return run_command(cmd)


def phase_4():
    """Fase 4: Suite completa + cobertura (nightly, con xdist y orden aleatorio)."""
    print("Fase 4: Suite completa + cobertura")
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "--tb=short",
        "-n",
        "auto",
        "--forked",
        "--randomly-seed=dynamic",
        "--cov",
        "--cov-branch",
        "--cov-report=term-missing:skip-covered",
    ]
    return run_command(cmd)


def main():
    parser = argparse.ArgumentParser(description="Pipeline QA para URA")
    parser.add_argument("--fase", type=int, choices=[0, 1, 2, 3, 4], help="Número de fase para ejecutar (0|1|2|3|4)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar acciones sin ejecutarlas")
    args = parser.parse_args()

    if args.dry_run:
        print("Modo dry-run activado. Solo se mostrarán las acciones sin ejecutarlas.")

    # Si no se especifica fase, ejecutar todas
    if args.fase is None:
        phases = [phase_0, phase_1, phase_2, phase_3, phase_4]
        for i, phase_func in enumerate(phases):
            print(f"\n=== Ejecutando Fase {i} ===")
            if not phase_func():
                print(f"Fase {i} fallida")
                sys.exit(1)
            time.sleep(0.5)  # Pequeña pausa entre fases
        print("\nTodas las fases completadas exitosamente.")
    else:
        # Ejecutar solo la fase especificada
        phases = [phase_0, phase_1, phase_2, phase_3, phase_4]
        if 0 <= args.fase < len(phases):
            print(f"\n=== Ejecutando Fase {args.fase} ===")
            if not phases[args.fase]():
                print(f"Fase {args.fase} fallida")
                sys.exit(1)
            print(f"\nFase {args.fase} completada exitosamente.")
        else:
            print(f"Fase {args.fase} no válida. Debe ser un número entre 0 y 4.")
            sys.exit(1)


if __name__ == "__main__":
    main()
