#!/usr/bin/env python3
"""
URA Integración Google Search
Integración real con Google Custom Search API
"""

import requests
from core.logging_config import get_logger

logger = get_logger("google_search", log_dir="./logs")


class GoogleSearchAPI:
    """Integración con Google Custom Search API"""

    def __init__(self, api_key: str, cx: str):
        """
        Inicializar cliente Google Search

        Args:
            api_key: API key de Google Cloud
            cx: Custom Search Engine ID
        """
        self.api_key = api_key
        self.cx = cx
        self.base_url = "https://www.googleapis.com/customsearch/v1"

    def buscar(self, query: str, num_results: int = 10) -> list[dict[str, str]]:
        """
        Buscar en Google

        Args:
            query: Consulta
            num_results: Número de resultados

        Returns:
            Lista de resultados
        """
        try:
            url = f"{self.base_url}"

            params = {"key": self.api_key, "cx": self.cx, "q": query, "num": num_results}

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()

            resultado = response.json()
            items = resultado.get("items", [])

            resultados = []
            for item in items:
                resultados.append(
                    {
                        "titulo": item.get("title", ""),
                        "url": item.get("link", ""),
                        "snippet": item.get("snippet", ""),
                    }
                )

            logger.info(f"Google search completado: {len(resultados)} resultados")
            return resultados

        except Exception as e:
            logger.error(f"Error en Google search: {e}")
            return []

    def verificar_disponibilidad(self) -> bool:
        """
        Verificar disponibilidad

        Returns:
            True si está disponible
        """
        try:
            resultado = self.buscar("test", 1)
            return len(resultado) > 0
        except Exception as e:
            logger.error(f"Error verificando disponibilidad Google: {e}")
            return False


# Instancia global (requiere API key y CX)
google_search = None


def configurar_google_search(api_key: str, cx: str):
    """Configurar Google Search"""
    global google_search
    google_search = GoogleSearchAPI(api_key, cx)


if __name__ == "__main__":
    # Test con API key simulada
    api = GoogleSearchAPI("test_key", "test_cx")
    print(f"Disponibilidad: {api.verificar_disponibilidad()}")
