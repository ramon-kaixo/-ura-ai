#!/usr/bin/env python3
"""
Pre-commit Hook - Tests de Regresión Automática (Memoria Técnica)
Ejecuta automáticamente los tests de URA antes de guardar cambios en el código.
Si algún test falla, el commit se rechaza.
"""

import subprocess
import sys
from pathlib import Path


def run_regression_tests():
    """Ejecutar tests de regresión"""
    print("🔄 Ejecutando Tests de Regresión Automática...")
    print("=" * 60)

    # Ejecutar STRESS_TEST_125.py
    test_file = Path(__file__).parent / "STRESS_TEST_125.py"

    try:
        result = subprocess.run(
            ["python", str(test_file)],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minutos máximo
        )

        # Analizar output para determinar si todos pasaron
        output = result.stdout + result.stderr

        # Buscar "Tasa de éxito" en el output
        if "Tasa de éxito:" in output:
            # Extraer el porcentaje
            for line in output.split("\n"):
                if "Tasa de éxito:" in line:
                    success_rate = line.split("Tasa de éxito:")[1].strip().replace("%", "")
                    try:
                        success_rate = float(success_rate)
                        if success_rate >= 100.0:
                            print("✅ Todos los tests pasaron - Commit permitido")
                            return True
                        else:
                            print(f"❌ Tests fallaron ({success_rate}% éxito) - Commit rechazado")
                            print("   Corrige los errores antes de continuar")
                            return False
                    except:
                        pass

        # Si no podemos determinar el éxito por el output, usar return code
        if result.returncode == 0:
            print("✅ Tests completados exitosamente - Commit permitido")
            return True
        else:
            print("❌ Tests fallaron - Commit rechazado")
            return False

    except subprocess.TimeoutExpired:
        print("❌ Timeout - Tests tardaron demasiado - Commit rechazado")
        return False
    except Exception as e:
        print(f"❌ Error ejecutando tests: {e}")
        return False


if __name__ == "__main__":
    success = run_regression_tests()
    sys.exit(0 if success else 1)
