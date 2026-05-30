#!/usr/bin/env python3
"""
URA Integración Ollama
Integración real con Ollama (policía y principal)
"""

import requests
from core.logging_config import get_logger
from core.model_config import get_active_model

logger = get_logger("ollama_integracion", log_dir="./logs")


class OllamaIntegracion:
    """Integración con Ollama"""

    def __init__(self, host: str = "localhost", port: int = 11434):
        """
        Inicializar cliente Ollama

        Args:
            host: Host de Ollama
            port: Puerto de Ollama
        """
        self.base_url = f"http://{host}:{port}"

    def consultar(self, peticion: str, modelo: str = None) -> str:
        """
        Consultar Ollama

        Args:
            peticion: Petición
            modelo: Modelo a usar (si es None, usa get_active_model())

        Returns:
            Respuesta de Ollama
        """
        if modelo is None:
            modelo = get_active_model()
        try:
            url = f"{self.base_url}/api/generate"

            data = {"model": modelo, "prompt": peticion, "stream": False}

            response = requests.post(url, json=data, timeout=60)
            response.raise_for_status()

            resultado = response.json()
            respuesta = resultado["response"]

            logger.info(f"Ollama consultado exitosamente ({modelo})")
            return respuesta

        except Exception as e:
            logger.error(f"Error consultando Ollama: {e}")
            return f"Error Ollama: {str(e)}"

    def consultar_policia(self, peticion: str) -> str:
        """Consultar Ollama policía"""
        return self.consultar(peticion, get_active_model())

    def consultar_principal(self, peticion: str) -> str:
        """Consultar Ollama principal"""
        return self.consultar(peticion, get_active_model())

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad de Ollama

        Returns:
            True si está disponible
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verificando disponibilidad Ollama: {e}")
            return False

    def listar_modelos(self) -> list:
        """
        Listar modelos disponibles

        Returns:
            Lista de modelos
        """
        try:
            url = f"{self.base_url}/api/tags"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            resultado = response.json()
            modelos = [m["name"] for m in resultado.get("models", [])]

            return modelos

        except Exception as e:
            logger.error(f"Error listando modelos Ollama: {e}")
            return []


# Instancias globales
ollama_policia = OllamaIntegracion()
ollama_principal = OllamaIntegracion()


if __name__ == "__main__":
    ollama = OllamaIntegracion()
    print(f"Disponibilidad: {ollama.verificar_disponibilidad()}")
    print(f"Modelos: {ollama.listar_modelos()}")
