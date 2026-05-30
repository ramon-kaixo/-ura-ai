#!/usr/bin/env python3
"""
URA Script de Instalación Automática
Instala y configura todo lo posible automáticamente
"""

import subprocess
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("instalacion_automatica", log_dir="./logs")


class InstalacionAutomatica:
    """Instalación Automática de URA"""

    def __init__(self):
        """Inicializar instalación"""
        self.base_dir = Path(__file__).parent.parent
        self.tareas_completadas = []
        self.tareas_pendientes = []

    def instalar_dependencias_python(self):
        """Instalar dependencias Python"""
        try:
            logger.info("Instalando dependencias Python...")
            subprocess.run(
                ["pip", "install", "-r", "requirements.txt"], cwd=self.base_dir, check=True
            )
            self.tareas_completadas.append("Dependencias Python instaladas")
            logger.info("Dependencias Python instaladas correctamente")
        except Exception as e:
            logger.error(f"Error instalando dependencias: {e}")
            self.tareas_pendientes.append("Instalar dependencias Python manualmente")

    def crear_directorios(self):
        """Crear directorios necesarios"""
        try:
            directorios = [
                "logs",
                "backups",
                "biblioteca/documentacion",
                "biblioteca/manuales",
                "data/historical",
                "data/models",
            ]

            for directorio in directorios:
                ruta = self.base_dir / directorio
                ruta.mkdir(parents=True, exist_ok=True)

            self.tareas_completadas.append("Directorios creados")
            logger.info("Directorios creados correctamente")
        except Exception as e:
            logger.error(f"Error creando directorios: {e}")

    def configurar_env(self):
        """Configurar archivo .env"""
        try:
            env_example = self.base_dir / ".env.example"
            env_file = self.base_dir / ".env"

            if env_example.exists() and not env_file.exists():
                import shutil

                shutil.copy(env_example, env_file)
                self.tareas_completadas.append("Archivo .env creado")
                logger.info("Archivo .env creado")
            elif env_file.exists():
                self.tareas_completadas.append("Archivo .env ya existe")
                logger.info("Archivo .env ya existe")
        except Exception as e:
            logger.error(f"Error configurando .env: {e}")

    def verificar_postgresql(self):
        """Verificar si PostgreSQL está instalado"""
        try:
            result = subprocess.run(["psql", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.tareas_completadas.append("PostgreSQL instalado")
                logger.info("PostgreSQL detectado")
                return True
        except Exception:
            pass

        self.tareas_pendientes.append("Instalar PostgreSQL")
        logger.warning("PostgreSQL no detectado - tarea pendiente")
        return False

    def verificar_ollama(self):
        """Verificar si Ollama está instalado"""
        try:
            result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
            if result.returncode == 0:
                self.tareas_completadas.append("Ollama instalado")
                logger.info("Ollama detectado")
                return True
        except Exception:
            pass

        self.tareas_pendientes.append("Instalar Ollama")
        logger.warning("Ollama no detectado - tarea pendiente")
        return False

    def ejecutar_instalacion(self):
        """Ejecutar instalación completa"""
        logger.info("Iniciando instalación automática...")

        # Tareas que puedo hacer
        self.crear_directorios()
        self.configurar_env()
        self.instalar_dependencias_python()

        # Tareas que requieren verificación
        self.verificar_postgresql()
        self.verificar_ollama()

        # Reporte
        self.generar_reporte()

    def generar_reporte(self):
        """Generar reporte de instalación"""
        reporte = {"completadas": self.tareas_completadas, "pendientes": self.tareas_pendientes}

        logger.info("=" * 50)
        logger.info("REPORTE DE INSTALACIÓN")
        logger.info("=" * 50)
        logger.info(f"Tareas completadas: {len(self.tareas_completadas)}")
        for tarea in self.tareas_completadas:
            logger.info(f"  ✅ {tarea}")

        logger.info(f"Tareas pendientes: {len(self.tareas_pendientes)}")
        for tarea in self.tareas_pendientes:
            logger.info(f"  ⏳ {tarea}")

        logger.info("=" * 50)

        return reporte


if __name__ == "__main__":
    instalacion = InstalacionAutomatica()
    instalacion.ejecutar_instalacion()
