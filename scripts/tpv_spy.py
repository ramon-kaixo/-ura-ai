#!/usr/bin/env python3
"""TPV Spy — espia pasivo para TPV R4 (Access) — extrae tablas clave y las guarda en SQLite local."""

import io
import logging
import os
import sqlite3
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger("TPVSpy")

# Configuracion rutas
ACCESS_DB_PATH = os.getenv("TPV_ACCESS_PATH", "/Volumes/Compartida/R4/data/R4.accdb")
LOCAL_DB = os.getenv("TPV_LOCAL_DB", "/opt/ura/data/tpv_history.db")
CONTROL_FILE = "/tmp/tpv_last_export.txt"
SMB_MOUNT_POINT = "/Volumes/Compartida"

# Tablas a espiar (nombres reales del TPV R4)
TABLAS_INTERES = [
    "Ventas",
    "DetalleVentas",
    "Articulos",
    "Familias",
    "Reservas",
    "Camareros",
]


def ensure_volume_mounted(mount_point: str = SMB_MOUNT_POINT, max_wait: int = 60) -> bool:
    """Espera hasta que el volumen SMB este montado.

    Args:
        mount_point: Punto de montaje a verificar.
        max_wait: Tiempo maximo de espera en segundos.

    Returns:
        True si el volumen esta montado, False si se agoto el tiempo.
    """
    waited = 0
    while not os.path.ismount(mount_point):
        if waited == 0:
            logger.info("Esperando a que el volumen SMB este montado...")
        time.sleep(5)
        waited += 5
        if waited > max_wait:
            logger.error("Volumen SMB no montado tras %d segundos.", max_wait)
            return False
    logger.info("Volumen SMB montado.")
    return True


def exportar_tabla(tabla: str) -> pd.DataFrame | None:
    """Usa mdb-export para volcar una tabla Access a DataFrame.

    Args:
        tabla: Nombre de la tabla Access.

    Returns:
        DataFrame con los datos o None si fallo.
    """
    try:
        cmd = f"mdb-export '{ACCESS_DB_PATH}' {tabla}"
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            df = pd.read_csv(io.StringIO(result.stdout), dtype=str)
            return df
        logger.error("Error exportando %s: %s", tabla, result.stderr.strip())
        return None
    except subprocess.TimeoutExpired:
        logger.error("Timeout exportando %s", tabla)
        return None
    except Exception as exc:
        logger.error("Excepcion exportando %s: %s", tabla, exc)
        return None


def guardar_en_sqlite(df: pd.DataFrame, tabla: str, if_exists: str = "append") -> None:
    """Guarda un DataFrame en la base de datos SQLite local.

    Args:
        df: DataFrame a guardar.
        tabla: Nombre de la tabla SQLite.
        if_exists: Comportamiento si la tabla existe (append/replace).
    """
    Path(LOCAL_DB).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(LOCAL_DB)
    df.to_sql(tabla, conn, if_exists=if_exists, index=False)
    conn.close()
    logger.info("%d registros guardados en tabla '%s'", len(df), tabla)


def main() -> None:
    """Bucle principal de sincronizacion pasiva del TPV R4."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    if not ensure_volume_mounted():
        sys.exit(1)

    if not os.path.exists(ACCESS_DB_PATH):
        logger.warning("Base de datos Access no encontrada: %s", ACCESS_DB_PATH)
        return

    logger.info("TPV Spy iniciado. Monitorizando: %s", ACCESS_DB_PATH)
    logger.info("Base de datos local: %s", LOCAL_DB)

    for tabla in TABLAS_INTERES:
        df = exportar_tabla(tabla)
        if df is not None and not df.empty:
            # Articulos y Familias se reemplazan (son maestros), el resto se anexa
            modo = "replace" if tabla in {"Articulos", "Familias", "Camareros"} else "append"
            guardar_en_sqlite(df, tabla, if_exists=modo)
        else:
            logger.debug("Tabla %s vacia o no accesible", tabla)

    # Guardar timestamp de ultima ejecucion
    with open(CONTROL_FILE, "w", encoding="utf-8") as fh:
        fh.write(datetime.now().isoformat())

    logger.info("Sincronizacion completada")


if __name__ == "__main__":
    main()
