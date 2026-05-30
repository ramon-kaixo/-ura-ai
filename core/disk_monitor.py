#!/usr/bin/env python3
"""
Módulo: core/disk_monitor.py
Propósito: Monitorea espacio en disco y envía alertas cuando baja del umbral configurado.
Dependencias principales: psutil, logging, datetime
Reglas especiales: Alertar solo una vez por umbral. No spam de notificaciones.
"""

import time
from typing import Any

import psutil

from core.logging_config import get_logger

logger = get_logger("disk_monitor", log_dir="./logs")


def monitorear() -> dict[str, Any]:
    """
    Monitorear espacio en disco

    Returns:
        Dict con {ok, gb_libres, gb_totales, estado}
        donde estado es "ok", "warning" o "critical"
    """
    try:
        usage = psutil.disk_usage("/")

        gb_totales = usage.total / (1024**3)
        gb_libres = usage.free / (1024**3)

        # Determinar estado
        if gb_libres < 1.0:
            estado = "critical"
        elif gb_libres < 5.0:
            estado = "warning"
        else:
            estado = "ok"

        logger.info(f"Disk monitor: {gb_libres:.2f} GB libres de {gb_totales:.2f} GB ({estado})")

        return {
            "ok": True,
            "gb_libres": gb_libres,
            "gb_totales": gb_totales,
            "estado": estado,
        }
    except Exception as e:
        logger.error(f"Error monitoreando disco: {e}")
        return {
            "ok": False,
            "gb_libres": 0.0,
            "gb_totales": 0.0,
            "estado": "error",
        }


def bucle(intervalo_segundos: int = 300) -> None:
    """
    Loop de monitoreo continuo

    Args:
        intervalo_segundos: Intervalo entre checks (default 300 = 5 minutos)
    """
    logger.info(f"Iniciando bucle de monitoreo (intervalo: {intervalo_segundos}s)")

    estado_anterior = None

    while True:
        resultado = monitorear()
        estado_actual = resultado["estado"]

        # Loggear solo si el estado cambió o es crítico
        if estado_actual != estado_anterior or estado_actual == "critical":
            if estado_actual == "critical":
                logger.critical(f"🚨 CRÍTICO: {resultado['gb_libres']:.2f} GB libres")
            elif estado_actual == "warning":
                logger.warning(f"⚠️ ADVERTENCIA: {resultado['gb_libres']:.2f} GB libres")
            else:
                logger.info(f"✅ OK: {resultado['gb_libres']:.2f} GB libres")

            estado_anterior = estado_actual

        time.sleep(intervalo_segundos)


if __name__ == "__main__":
    print("=== TEST DISK MONITOR ===")

    # Test monitorear
    resultado = monitorear()
    print(f"Monitoreo: {resultado}")

    # Test bucle (comentado para no bloquear)
    # bucle(intervalo_segundos=10)
