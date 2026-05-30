#!/usr/bin/env python3
"""
Ejecutor de Herramientas Automáticas - URA App
Ejecuta black, isort, ruff, mypy, bandit, pylint
"""

import subprocess
import sys


def run_black(archivo: str) -> bool:
    """Ejecutar black"""
    try:
        subprocess.run([sys.executable, "-m", "black", archivo], check=True, capture_output=True)
        print("✅ Black formateó el archivo")
        return True
    except subprocess.CalledProcessError:
        print("❌ Black falló")
        return False


def run_isort(archivo: str) -> bool:
    """Ejecutar isort"""
    try:
        subprocess.run([sys.executable, "-m", "isort", archivo], check=True, capture_output=True)
        print("✅ isort ordenó los imports")
        return True
    except subprocess.CalledProcessError:
        print("❌ isort falló")
        return False


def run_ruff(archivo: str) -> bool:
    """Ejecutar ruff"""
    try:
        subprocess.run(
            [sys.executable, "-m", "ruff", "check", archivo], check=True, capture_output=True
        )
        print("✅ ruff verificó el código")
        return True
    except subprocess.CalledProcessError:
        print("❌ ruff encontró problemas")
        return False


def run_mypy(archivo: str) -> bool:
    """Ejecutar mypy"""
    try:
        subprocess.run([sys.executable, "-m", "mypy", archivo], check=True, capture_output=True)
        print("✅ mypy verificó los tipos")
        return True
    except subprocess.CalledProcessError:
        print("❌ mypy encontró problemas de tipo")
        return False


def run_bandit(archivo: str) -> bool:
    """Ejecutar bandit"""
    try:
        subprocess.run([sys.executable, "-m", "bandit", archivo], check=True, capture_output=True)
        print("✅ bandit verificó seguridad")
        return True
    except subprocess.CalledProcessError:
        print("❌ bandit encontró problemas de seguridad")
        return False


def run_pylint(archivo: str) -> bool:
    """Ejecutar pylint"""
    try:
        subprocess.run([sys.executable, "-m", "pylint", archivo], check=True, capture_output=True)
        print("✅ pylint verificó calidad")
        return True
    except subprocess.CalledProcessError:
        print("❌ pylint encontró problemas de calidad")
        return False


def run_all_tools(archivo: str) -> Dict:
    """Ejecutar todas las herramientas"""
    print(f"\n=== EJECUTANDO HERRAMIENTAS EN {archivo} ===\n")

    resultados = {
        "black": run_black(archivo),
        "isort": run_isort(archivo),
        "ruff": run_ruff(archivo),
        "mypy": run_mypy(archivo),
        "bandit": run_bandit(archivo),
        "pylint": run_pylint(archivo),
    }

    return resultados


if __name__ == "__main__":
    if len(sys.argv) > 1:
        archivo = sys.argv[1]
        run_all_tools(archivo)
    else:
        print("Uso: python run_tools.py <archivo>")
