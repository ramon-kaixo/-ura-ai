#!/usr/bin/env python3
"""
Script para filtrar test suites usando marcadores pytest.
Uso:
  python3 marker_filter.py unit      # Solo tests unitarios
  python3 marker_filter.py integration # Tests de integracion
  python3 marker_filter.py contracts   # Test de contratos
  python3 marker_filter.py all         # Todos los tests (por defecto)
"""

import subprocess
import sys


def get_test_count():
    """Obtener numero total de test en el proyecto"""
    result = subprocess.run([
        "python3", "-m", "pytest", "--collect-only", "-q"
    ], capture_output=True, text=True, check=False)

    for line in result.stdout.split("\n"):
        if "tests collected" in line:
            return int(line.split()[0])
    return 0


def main():
    marker = sys.argv[1] if len(sys.argv) > 1 else "all"

    # Mapeo de marcadores a patrones
    markers_map = {
        "unit": "not slow and not integration and not contract",
        "integration": "integration",
        "contract": "contract",
        "slow": "slow",
        "all": ""
    }

    if marker == "all":
        cmd = ["python3", "-m", "pytest", "-q"]
    else:
        pattern = markers_map.get(marker, "")
        if pattern:
            cmd = ["python3", "-m", "pytest", f"-k {pattern}", "-q"]
        else:
            # Si es un marcador personalizado
            cmd = ["python3", "-m", "pytest", f"-k {marker}", "-q"]

    print(f" Ejecutando: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    print(result.stdout)
    if result.stderr:
        print("Errores:", result.stderr)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
