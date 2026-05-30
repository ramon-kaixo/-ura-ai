#!/usr/bin/env python3
"""
URA Integración DeepSeek API
Integración real con DeepSeek API
"""

import requests
from core.logging_config import get_logger

logger = get_logger("deepseek_api", log_dir="./logs")


class DeepSeekAPI:
    """Integración con DeepSeek API"""

    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com/v1"):
        """
        Inicializar cliente DeepSeek

        Args:
            api_key: API key de DeepSeek
            base_url: URL base de la API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def consultar(self, peticion: str, modelo: str = "deepseek-chat") -> str:
        """
        Consultar DeepSeek

        Args:
            peticion: Petición
            modelo: Modelo a usar

        Returns:
            Respuesta de DeepSeek
        """
        try:
            url = f"{self.base_url}/chat/completions"

            data = {
                "model": modelo,
                "messages": [{"role": "user", "content": peticion}],
                "temperature": 0.7,
            }

            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()

            resultado = response.json()
            respuesta = resultado["choices"][0]["message"]["content"]

            logger.info("DeepSeek consultado exitosamente")
            return respuesta

        except Exception as e:
            logger.error(f"Error consultando DeepSeek: {e}")
            return f"Error DeepSeek: {str(e)}"

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad de DeepSeek

        Returns:
            True si está disponible
        """
        try:
            response = requests.get(f"{self.base_url}/models", headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verificando disponibilidad DeepSeek: {e}")
            return False


# Instancia global (requiere API key)
deepseek_api = None


def configurar_deepseek(api_key: str):
    """Configurar DeepSeek API"""
    global deepseek_api
    deepseek_api = DeepSeekAPI(api_key)


if __name__ == "__main__":
    # Test con API key simulada
    api = DeepSeekAPI("test_key")
    print(f"Disponibilidad: {api.verificar_disponibilidad()}")


# Inicializar desde variable de entorno
import os

_key = os.getenv("DEEPSEEK_API_KEY")
if _key:
    configurar_deepseek(_key)
