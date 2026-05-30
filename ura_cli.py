#!/usr/bin/env python3
"""
URA CLI - Interfaz de línea de comandos para URA

Menú interactivo para:
- Iniciar URA (main_final.py)
- Iniciar Panel Web (ura_panel.py)
- Ejecutar tests (pytest tests/)
- Ver estado de servicios (Ollama, OpenClaw)
"""

import logging
import subprocess
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


class URACLI:
    """Interfaz de línea de comandos de URA."""

    def __init__(self):
        self.project_root = Path(__file__).parent

    def show_menu(self):
        """Muestra el menú principal."""
        print("\n" + "=" * 50)
        print("URA - CLI")
        print("=" * 50)
        print("1. Iniciar URA (main_final.py)")
        print("2. Iniciar Panel Web (ura_panel.py)")
        print("3. Ejecutar todos los tests (pytest tests/)")
        print("4. Ver estado de servicios (Ollama, OpenClaw)")
        print("5. Salir")
        print("=" * 50)

    def start_ura(self):
        """Inicia URA (main_final.py)."""
        print("\n🚀 Iniciando URA...")
        try:
            subprocess.run(
                [sys.executable, str(self.project_root / "main_final.py")], cwd=self.project_root
            )
        except KeyboardInterrupt:
            print("\n⚠️  URA interrumpido por el usuario")
        except Exception as e:
            print(f"❌ Error iniciando URA: {e}")

    def start_panel(self):
        """Inicia el Panel Web (ura_panel.py)."""
        print("\n🌐 Iniciando Panel Web...")
        try:
            subprocess.run(
                [sys.executable, str(self.project_root / "ura_panel.py")], cwd=self.project_root
            )
        except KeyboardInterrupt:
            print("\n⚠️  Panel Web interrumpido por el usuario")
        except Exception as e:
            print(f"❌ Error iniciando Panel Web: {e}")

    def run_tests(self):
        """Ejecuta todos los tests."""
        print("\n🧪 Ejecutando tests...")
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "tests/", "-v"],
                cwd=self.project_root,
                capture_output=False,
            )
            if result.returncode == 0:
                print("\n✅ Todos los tests pasaron")
            else:
                print(f"\n❌ Tests fallidos (exit code: {result.returncode})")
        except Exception as e:
            print(f"❌ Error ejecutando tests: {e}")

    def check_services(self):
        """Verifica el estado de servicios."""
        print("\n🔍 Verificando estado de servicios...")

        # Verificar Ollama
        print("\n--- Ollama ---")
        try:
            result = subprocess.run(
                ["curl", "-s", "http://localhost:11434/api/tags"], capture_output=True, timeout=5
            )
            if result.returncode == 0:
                print("✅ Ollama: Activo")
            else:
                print("❌ Ollama: Inactivo")
        except Exception as e:
            print(f"❌ Ollama: No disponible ({e})")

        # Verificar OpenClaw
        print("\n--- OpenClaw ---")
        try:
            result = subprocess.run(["openclaw", "--version"], capture_output=True, timeout=5)
            if result.returncode == 0:
                print("✅ OpenClaw: Disponible")
                print(f"   Versión: {result.stdout.decode().strip()}")
            else:
                print("❌ OpenClaw: No disponible")
        except Exception as e:
            print(f"❌ OpenClaw: No disponible ({e})")

        print("\n" + "=" * 50)

    def run(self):
        """Ejecuta el CLI."""
        while True:
            self.show_menu()
            choice = input("\nSelecciona una opción (1-5): ").strip()

            if choice == "1":
                self.start_ura()
            elif choice == "2":
                self.start_panel()
            elif choice == "3":
                self.run_tests()
            elif choice == "4":
                self.check_services()
            elif choice == "5":
                print("\n👋 ¡Hasta pronto!")
                sys.exit(0)
            else:
                print("\n❌ Opción no válida. Por favor, selecciona 1-5.")


def main():
    """Punto de entrada principal."""
    logging.basicConfig(level=logging.INFO)
    cli = URACLI()
    cli.run()


if __name__ == "__main__":
    main()
