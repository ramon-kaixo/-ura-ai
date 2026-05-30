#!/usr/bin/env python3
"""
URA Integración Gemini API
Integración real con Gemini API (Google)
"""

import requests
from core.logging_config import get_logger

logger = get_logger("gemini_api", log_dir="./logs")


class GeminiAPI:
    """Integración con Gemini API"""

    def __init__(
        self, api_key: str, base_url: str = "https://generativelanguage.googleapis.com/v1beta"
    ):
        """
        Inicializar cliente Gemini

        Args:
            api_key: API key de Google
            base_url: URL base de la API
        """
        self.api_key = api_key
        self.base_url = base_url

    def consultar(self, peticion: str, modelo: str = "gemini-pro") -> str:
        """
        Consultar Gemini

        Args:
            peticion: Petición
            modelo: Modelo a usar

        Returns:
            Respuesta de Gemini
        """
        try:
            url = f"{self.base_url}/models/{modelo}:generateContent?key={self.api_key}"

            data = {"contents": [{"parts": [{"text": peticion}]}]}

            response = requests.post(url, json=data, timeout=30)
            response.raise_for_status()

            resultado = response.json()
            respuesta = resultado["candidates"][0]["content"]["parts"][0]["text"]

            logger.info("Gemini consultado exitosamente")
            return respuesta

        except Exception as e:
            logger.error(f"Error consultando Gemini: {e}")
            return f"Error Gemini: {str(e)}"

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad de Gemini

        Returns:
            True si está disponible
        """
        try:
            url = f"{self.base_url}/models?key={self.api_key}"
            response = requests.get(url, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verificando disponibilidad Gemini: {e}")
            return False


# Instancia global (requiere API key)
gemini_api = None


def configurar_gemini(api_key: str):
    """Configurar Gemini API"""
    global gemini_api
    gemini_api = GeminiAPI(api_key)


if __name__ == "__main__":
    # Test con API key simulada
    api = GeminiAPI("test_key")
    print(f"Disponibilidad: {api.verificar_disponibilidad()}")


# Inicializar desde variable de entorno
import os

_key = os.getenv("GEMINI_API_KEY")
if _key:
    configurar_gemini(_key)
