#!/usr/bin/env python3
"""
URA - Cloud Backup
Backup a iCloud via brctl (macOS only)
"""

import sys
import time
from pathlib import Path
from typing import Any

from core.ejecutor_seguro import ejecutar
from core.logging_config import get_logger

logger = get_logger("cloud_backup", log_dir="./logs")


def hacer_backup(origen: str = "~/URA/ura_ia_1972") -> dict[str, Any]:
    """
    Hace backup a iCloud de los datos de URA.

    Args:
        origen: Ruta de origen (default ~/URA/ura_ia_1972)

    Returns:
        Dict con {ok, archivos, duracion_segundos, error}
    """
    # Solo macOS
    if sys.platform != "darwin":
        logger.error("Cloud backup solo disponible en macOS")
        return {
            "ok": False,
            "archivos": 0,
            "duracion_segundos": 0.0,
            "error": "Solo macOS",
        }

    start_time = time.time()
    origen_path = Path(origen).expanduser()
    icloud_path = Path.home() / "Library/Mobile Documents/com~apple~CloudDocs/URA_Backup/"

    logger.info(f"Iniciando backup: {origen_path} -> {icloud_path}")

    # Verificar que iCloud está disponible con brctl
    try:
        resultado = ejecutar("brctl status")
        if not resultado["ok"]:
            logger.error(f"iCloud no disponible: {resultado['stderr']}")
            return {
                "ok": False,
                "archivos": 0,
                "duracion_segundos": 0.0,
                "error": f"iCloud no disponible: {resultado['stderr']}",
            }
        logger.info("iCloud disponible (brctl status OK)")
    except Exception as e:
        logger.error(f"Error verificando iCloud con brctl: {e}")
        return {
            "ok": False,
            "archivos": 0,
            "duracion_segundos": 0.0,
            "error": f"Error verificando iCloud: {str(e)}",
        }

    # Crear directorio de backup si no existe
    try:
        icloud_path.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        logger.error(f"Error creando directorio de backup: {e}")
        return {
            "ok": False,
            "archivos": 0,
            "duracion_segundos": 0.0,
            "error": f"Error creando directorio: {str(e)}",
        }

    # Ejecutar rsync
    try:
        comando = f"rsync -av --delete {origen_path}/ {icloud_path}"
        resultado = ejecutar(comando, timeout=300)  # 5 minutos timeout

        if resultado["ok"]:
            # Contar archivos copiados
            archivos = len(list(icloud_path.rglob("*")))
            duracion = time.time() - start_time

            logger.info(f"Backup completado: {archivos} archivos, {duracion:.2f}s")

            return {
                "ok": True,
                "archivos": archivos,
                "duracion_segundos": duracion,
                "error": None,
            }
        else:
            logger.error(f"rsync falló: {resultado['stderr']}")
            return {
                "ok": False,
                "archivos": 0,
                "duracion_segundos": time.time() - start_time,
                "error": f"rsync falló: {resultado['stderr']}",
            }
    except Exception as e:
        logger.error(f"Error ejecutando rsync: {e}")
        return {
            "ok": False,
            "archivos": 0,
            "duracion_segundos": time.time() - start_time,
            "error": f"Error ejecutando rsync: {str(e)}",
        }


if __name__ == "__main__":
    print("=== TEST CLOUD BACKUP ===")

    # Test hacer_backup
    resultado = hacer_backup()
    print(f"Backup: {resultado}")
