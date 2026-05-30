#!/usr/bin/env python3
"""
Reparador Automático URA
Repara automáticamente problemas detectados
"""

import subprocess
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).parent.parent


class ReparadorAutomatico:
    """Reparador automático"""

    def __init__(self):
        self.project_dir = PROJECT_DIR

    def reparar_redis(self) -> bool:
        """Intenta reparar Redis"""
        try:
            subprocess.run(["redis-server", "--daemonize yes"], check=True)
            return True
        except:
            return False

    def reparar_ollama(self) -> bool:
        """Intenta reparar Ollama"""
        try:
            # Intentar reiniciar Ollama
            subprocess.run(["pkill", "-f", "ollama"], capture_output=True)
            subprocess.run(["ollama", "serve"], capture_output=True)
            return True
        except:
            return False

    def reparar_base_datos(self) -> bool:
        """Intenta reparar base de datos"""
        try:
            db_path = self.project_dir / "board.db"
            if not db_path.exists():
                # Crear base de datos vacía
                import sqlite3

                conn = sqlite3.connect(db_path)
                conn.close()
            return True
        except:
            return False

    def reparar_permisos(self) -> bool:
        """Repara permisos de archivos"""
        try:
            # Dar permisos de ejecución a scripts
            scripts_dir = self.project_dir / "scripts"
            for script in scripts_dir.glob("*.py"):
                script.chmod(0o755)
            return True
        except:
            return False

    def ejecutar_reparacion_completa(self) -> dict:
        """Ejecuta reparación completa automática"""
        reparaciones = []

        print("🔧 Ejecutando reparación automática...")

        # Redis
        if self.reparar_redis():
            reparaciones.append("redis")

        # Ollama
        if self.reparar_ollama():
            reparaciones.append("ollama")

        # Base de datos
        if self.reparar_base_datos():
            reparaciones.append("base_datos")

        # Permisos
        if self.reparar_permisos():
            reparaciones.append("permisos")

        return {
            "timestamp": datetime.now().isoformat(),
            "reparaciones_exitosas": len(reparaciones),
            "reparaciones": reparaciones,
        }


if __name__ == "__main__":
    reparador = ReparadorAutomatico()
    resultado = reparador.ejecutar_reparacion_completa()

    print(f"\n✅ Reparaciones: {resultado['reparaciones_exitosas']}")
    for r in resultado["reparaciones"]:
        print(f"   - {r}")
