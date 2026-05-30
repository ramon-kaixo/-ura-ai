#!/usr/bin/env python3
"""
URA Integración Claude API
Integración real con Claude API (Anthropic)
"""

from typing import Optional

import requests
from core.logging_config import get_logger

logger = get_logger("claude_api", log_dir="./logs")


class ClaudeAPI:
    """Integración con Claude API"""

    def __init__(self, api_key: str, base_url: str = "https://api.anthropic.com/v1"):
        """
        Inicializar cliente Claude

        Args:
            api_key: API key de Anthropic
            base_url: URL base de la API
        """
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }

    def consultar(self, peticion: str, modelo: str = "claude-3-sonnet-20240229") -> str:
        """
        Consultar Claude

        Args:
            peticion: Petición
            modelo: Modelo a usar

        Returns:
            Respuesta de Claude
        """
        try:
            url = f"{self.base_url}/messages"

            data = {
                "model": modelo,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": peticion}],
            }

            response = requests.post(url, headers=self.headers, json=data, timeout=30)
            response.raise_for_status()

            resultado = response.json()
            respuesta = resultado["content"][0]["text"]

            logger.info("Claude consultado exitosamente")
            return respuesta

        except Exception as e:
            logger.error(f"Error consultando Claude: {e}")
            return f"Error Claude: {str(e)}"

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad de Claude

        Returns:
            True si está disponible
        """
        try:
            # Claude no tiene endpoint de models, usamos una petición simple
            url = f"{self.base_url}/messages"
            data = {
                "model": "claude-3-sonnet-20240229",
                "max_tokens": 10,
                "messages": [{"role": "user", "content": "Hi"}],
            }
            response = requests.post(url, headers=self.headers, json=data, timeout=10)
            return response.status_code in [200, 400]  # 400 por API key inválida pero API responde
        except Exception as e:
            logger.error(f"Error verificando disponibilidad Claude: {e}")
            return False


# Instancia global (requiere API key)
claude_api: Optional["ClaudeAPI"] = None


def configurar_claude(api_key: str):
    """Configurar Claude API"""
    global claude_api
    claude_api = ClaudeAPI(api_key)


if __name__ == "__main__":
    # Test con API key simulada
    api = ClaudeAPI("test_key")
    print(f"Disponibilidad: {api.verificar_disponibilidad()}")


# Inicializar desde variable de entorno
import os

_key = os.getenv("ANTHROPIC_API_KEY")
if _key:
    configurar_claude(_key)
