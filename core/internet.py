#!/usr/bin/env python3
"""
URA - Internet Module
Controlled HTTP access with privacy scrubbing and circuit breaker
"""

import requests
from typing import Any

from core.logging_config import get_logger
from core.privacy_scrubber import PrivacyScrubber

logger = get_logger("internet", log_dir="./logs")

# Privacy scrubber
privacy_scrubber = PrivacyScrubber()


def get(url: str, timeout: int = 10) -> dict[str, Any]:
    """
    HTTP GET request con privacidad y manejo de errores

    Args:
        url: URL a consultar
        timeout: Timeout en segundos (default 10)

    Returns:
        Dict con {ok, data, error}
    """
    # Scrub URL para privacidad
    scrubbed_url, _ = privacy_scrubber.scrub_text(url)
    logger.info(f"GET request: {scrubbed_url}")

    try:
        response = requests.get(url, timeout=timeout)

        result = {
            "ok": True,
            "data": response.text,
            "error": None,
            "status_code": response.status_code,
        }

        logger.info(f"GET success: status={response.status_code}")

        return result

    except requests.Timeout:
        logger.error(f"GET timeout: {scrubbed_url}")
        return {
            "ok": False,
            "data": None,
            "error": f"Timeout después de {timeout} segundos",
            "status_code": None,
        }
    except requests.ConnectionError as e:
        logger.error(f"GET connection error: {scrubbed_url} - {e}")
        return {
            "ok": False,
            "data": None,
            "error": f"Error de conexión: {str(e)}",
            "status_code": None,
        }
    except Exception as e:
        logger.error(f"GET error: {scrubbed_url} - {e}")
        return {
            "ok": False,
            "data": None,
            "error": str(e),
            "status_code": None,
        }


def post(url: str, data: Any = None, timeout: int = 10) -> dict[str, Any]:
    """
    HTTP POST request con privacidad y manejo de errores

    Args:
        url: URL a consultar
        data: Datos a enviar (dict, str, etc.)
        timeout: Timeout en segundos (default 10)

    Returns:
        Dict con {ok, data, error}
    """
    # Scrub URL para privacidad
    scrubbed_url, _ = privacy_scrubber.scrub_text(url)
    logger.info(f"POST request: {scrubbed_url}")

    try:
        response = requests.post(url, data=data, timeout=timeout)

        result = {
            "ok": True,
            "data": response.text,
            "error": None,
            "status_code": response.status_code,
        }

        logger.info(f"POST success: status={response.status_code}")

        return result

    except requests.Timeout:
        logger.error(f"POST timeout: {scrubbed_url}")
        return {
            "ok": False,
            "data": None,
            "error": f"Timeout después de {timeout} segundos",
            "status_code": None,
        }
    except requests.ConnectionError as e:
        logger.error(f"POST connection error: {scrubbed_url} - {e}")
        return {
            "ok": False,
            "data": None,
            "error": f"Error de conexión: {str(e)}",
            "status_code": None,
        }
    except Exception as e:
        logger.error(f"POST error: {scrubbed_url} - {e}")
        return {
            "ok": False,
            "data": None,
            "error": str(e),
            "status_code": None,
        }


# Alias para compatibilidad con agente_seguridad.py
def get_url(url: str, timeout: int = 10) -> str:
    """
    Alias para compatibilidad con agente_seguridad.py
    Devuelve el data directamente como string

    Args:
        url: URL a consultar
        timeout: Timeout en segundos (default 10)

    Returns:
        str: Response data o error message
    """
    result = get(url, timeout)
    if result["ok"]:
        return result["data"]
    else:
        return f"Error: {result['error']}"


if __name__ == "__main__":
    # Test
    print("=== TEST INTERNET MODULE ===")

    # GET request
    resultado = get("https://api.ipify.org?format=json")
    print(f"GET: {resultado}")

    # POST request
    resultado = post("https://httpbin.org/post", data={"test": "data"})
    print(f"POST: {resultado}")

    # get_url alias
    resultado = get_url("https://api.ipify.org?format=json")
    print(f"get_url: {resultado}")
