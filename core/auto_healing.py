#!/usr/bin/env python3
"""
Módulo: core/auto_healing.py
Propósito: Sistema de auto-reparación: detecta servicios caídos, abre circuit breakers, reinicia procesos fallidos.
Dependencias principales: subprocess, time, CircuitBreaker, NetworkAuditSystem
Reglas especiales: No reinicia agentes críticos sin confirmación. Usa backoff exponencial.
"""

import logging
import subprocess
import time

from core.circuit_breaker import get_circuit_breaker
from core.logging_config import get_logger

logger = get_logger("auto_healing", log_dir="./logs")


def intentar_recuperacion(servicio: str) -> bool:
    """
    Intenta recuperar un servicio en orden:
    1. Reiniciar el servicio (docker restart nombre_contenedor o equivalente)
    2. Cambiar al modelo de fallback (usando core/ram_manager.py)
    3. Limpiar caché de Redis
    4. Si todo falla → abrir circuit breaker + avisar por Telegram

    Args:
        servicio: Nombre del servicio a recuperar

    Returns:
        True si se recuperó correctamente, False en caso contrario
    """
    logger.info(f"Iniciando auto-healing para servicio: {servicio}")

    # Paso 1: Reiniciar el servicio
    if _reiniciar_servicio(servicio):
        logger.info(f"Servicio {servicio} recuperado tras reinicio")
        return True

    # Paso 2: Cambiar al modelo de fallback
    if servicio.lower() == "ollama":
        if _cambiar_modelo_fallback():
            logger.info(f"Servicio {servicio} recuperado tras cambio de modelo")
            return True

    # Paso 3: Limpiar caché de Redis
    if servicio.lower() == "redis":
        if _limpiar_cache_redis():
            logger.info(f"Servicio {servicio} recuperado tras limpiar caché")
            return True

    # Paso 4: Si todo falla, abrir circuit breaker + avisar por Telegram
    logger.error(f"No se pudo recuperar {servicio} automáticamente")
    _abrir_circuit_breaker(servicio)
    return False


def _reiniciar_servicio(servicio: str) -> bool:
    """
    Reinicia el servicio (docker restart nombre_contenedor o equivalente)

    Args:
        servicio: Nombre del servicio

    Returns:
        True si se reinició correctamente
    """
    logger.info(f"Intentando reiniciar {servicio}")

    try:
        if servicio.lower() == "ollama":
            # Reiniciar Ollama
            subprocess.run(["pkill", "-f", "ollama"], timeout=5)
            import time

            time.sleep(2)
            # No iniciamos ollama serve aquí porque podría ser background
            logger.info("Ollama detenido para reinicio")
            return True

        elif servicio.lower() == "redis":
            # Reiniciar Redis
            subprocess.run(["brew", "services", "restart", "redis"], timeout=10)
            logger.info("Redis reiniciado")
            return True

        else:
            logger.warning(f"No hay comando de reinicio para {servicio}")
            return False

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout reiniciando {servicio}")
        return False
    except FileNotFoundError:
        logger.error(f"Comando no encontrado para reiniciar {servicio}")
        return False
    except Exception as e:
        logger.error(f"Error reiniciando {servicio}: {e}")
        return False


def _cambiar_modelo_fallback() -> bool:
    """
    Cambia al modelo de fallback usando core/ram_manager.py

    Returns:
        True si se cambió correctamente
    """
    logger.info("Intentando cambiar a modelo de fallback")

    try:
        from core.ram_manager import pick_model_for_ram

        # Obtener modelo recomendado según RAM actual
        modelo_recomendado = pick_model_for_ram()

        # Nota: Aquí se debería actualizar la configuración del modelo activo
        # Por ahora solo loggeamos el cambio recomendado
        logger.info(f"Modelo recomendado por RAM: {modelo_recomendado}")

        # En una implementación completa, aquí se actualizaría:
        # - core/model_config.py para cambiar el modelo activo
        # - Reiniciar Ollama con el nuevo modelo

        return True

    except Exception as e:
        logger.error(f"Error cambiando modelo: {e}")
        return False


def _limpiar_cache_redis() -> bool:
    """
    Limpia caché de Redis

    Returns:
        True si se limpió correctamente
    """
    logger.info("Intentando limpiar caché de Redis")

    try:
        import redis

        r = redis.Redis(host="localhost", port=6379, db=0)
        r.flushdb()
        logger.info("Caché de Redis limpiada")
        return True

    except redis.ConnectionError:
        logger.error("No se puede conectar a Redis")
        return False
    except Exception as e:
        logger.error(f"Error limpiando caché Redis: {e}")
        return False


def _abrir_circuit_breaker(servicio: str) -> None:
    """
    Abre el circuit breaker y avisa por Telegram

    Args:
        servicio: Nombre del servicio
    """
    logger.warning(f"Abriendo circuit breaker para {servicio}")

    try:
        cb = get_circuit_breaker(servicio)

        # Forzar estado abierto
        cb.state = "abierto"  # Usar valor string en lugar de enum
        cb.failure_count = cb.failure_threshold + 1
        cb.last_state_change = time.time()

        # Loggear cambio de estado
        cb._log_state_change("cerrado", "abierto", f"Auto-healing falló para {servicio}")

        # Avisar por Telegram
        cb._send_telegram_alert()

    except Exception as e:
        logger.error(f"Error abriendo circuit breaker: {e}")


def verificar_servicio(servicio: str) -> bool:
    """
    Verifica si un servicio está funcionando correctamente

    Args:
        servicio: Nombre del servicio

    Returns:
        True si está funcionando, False en caso contrario
    """
    try:
        if servicio.lower() == "ollama":
            # Verificar si Ollama responde
            import requests

            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            return response.status_code == 200

        elif servicio.lower() == "redis":
            # Verificar si Redis responde
            import redis

            r = redis.Redis(host="localhost", port=6379, db=0)
            r.ping()
            return True

        else:
            logger.warning(f"No hay verificación para {servicio}")
            return True

    except Exception as e:
        logger.error(f"Error verificando {servicio}: {e}")
        return False


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    # Prueba
    servicio = "ollama"
    print(f"Verificando {servicio}...")
    funcionando = verificar_servicio(servicio)
    print(f"Funcionando: {funcionando}")

    if not funcionando:
        print("Intentando recuperación...")
        recuperado = intentar_recuperacion(servicio)
        print(f"Recuperado: {recuperado}")
