#!/usr/bin/env python3
"""
URA Integración ChatGPT API
Integración real con ChatGPT API (OpenAI)
"""

import requests
from core.logging_config import get_logger

logger = get_logger("chatgpt_api", log_dir="./logs")


class ChatGPTAPI:
    """Integración con ChatGPT API"""

    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        """
        Inicializar cliente ChatGPT

        Args:
            api_key: API key de OpenAI
            base_url: URL base de la API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    def consultar(self, peticion: str, modelo: str = "gpt-4") -> str:
        """
        Consultar ChatGPT

        Args:
            peticion: Petición
            modelo: Modelo a usar

        Returns:
            Respuesta de ChatGPT
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

            logger.info("ChatGPT consultado exitosamente")
            return respuesta

        except Exception as e:
            logger.error(f"Error consultando ChatGPT: {e}")
            return f"Error ChatGPT: {str(e)}"

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad de ChatGPT

        Returns:
            True si está disponible
        """
        try:
            url = f"{self.base_url}/models"
            response = requests.get(url, headers=self.headers, timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verificando disponibilidad ChatGPT: {e}")
            return False


# Instancia global (requiere API key)
chatgpt_api = None


def configurar_chatgpt(api_key: str):
    """Configurar ChatGPT API"""
    global chatgpt_api
    chatgpt_api = ChatGPTAPI(api_key)


if __name__ == "__main__":
    # Test con API key simulada
    api = ChatGPTAPI("test_key")
    print(f"Disponibilidad: {api.verificar_disponibilidad()}")


# Inicializar desde variable de entorno
import os

_key = os.getenv("OPENAI_API_KEY")
if _key:
    configurar_chatgpt(_key)
