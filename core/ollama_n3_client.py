#!/usr/bin/env python3
"""
Cliente directo a Ollama para N3 (reemplazo de OpenClaw).

Este cliente usa Ollama directamente para búsquedas N3, evitando
la complejidad y timeouts de OpenClaw embedded.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any
import aiohttp

logger = logging.getLogger("ollama_n3_client")

# Configuración por defecto
DEFAULT_BASE_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "llama3.2:latest"
DEFAULT_TIMEOUT = 60
MAX_RETRIES = 3


@dataclass
class OllamaSearchResult:
    """Resultado de búsqueda Ollama."""

    query: str
    response: str
    elapsed: float
    source: str
    success: bool
    error: str | None = None
    tokens: int = 0
    model: str = ""


class OllamaN3Client:
    """Cliente async directo a Ollama para N3."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        model: str = DEFAULT_MODEL,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.max_retries = max_retries
        self.session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Context manager entry."""
        self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=self.timeout))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self.session:
            await self.session.close()

    async def health_check(self) -> bool:
        """
        Verifica si Ollama está respondiendo.

        Returns:
            True si healthy, False si no.
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                return resp.status == 200
        except Exception as e:
            logger.warning(f"Health check falló: {e}")
            return False

    async def search(
        self, query: str, model: str | None = None, max_tokens: int = 2000
    ) -> OllamaSearchResult:
        """
        Ejecuta búsqueda en Ollama.

        Args:
            query: Query de búsqueda
            model: Modelo a usar (por defecto self.model)
            max_tokens: Máximo de tokens (para validación)

        Returns:
            OllamaSearchResult con respuesta
        """
        start = time.monotonic()
        last_error = None
        model_to_use = model or self.model

        for attempt in range(self.max_retries):
            try:
                if not self.session:
                    self.session = aiohttp.ClientSession(
                        timeout=aiohttp.ClientTimeout(total=self.timeout)
                    )

                payload = {
                    "model": model_to_use,
                    "prompt": query,
                    "stream": False,
                    "options": {"num_predict": max_tokens},
                }

                async with self.session.post(f"{self.base_url}/api/generate", json=payload) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        elapsed = time.monotonic() - start

                        response_text = data.get("response", "")
                        tokens = len(response_text.split())

                        logger.info(
                            f"[OLLAMA] Respuesta recibida en {elapsed:.2f}s - {tokens} tokens"
                        )

                        return OllamaSearchResult(
                            query=query,
                            response=response_text,
                            elapsed=elapsed,
                            source="ollama_direct",
                            success=True,
                            tokens=tokens,
                            model=model_to_use,
                        )
                    else:
                        error_text = await resp.text()
                        last_error = f"HTTP {resp.status}: {error_text}"
                        logger.warning(f"Intento {attempt + 1}: {last_error}")
                        if attempt < self.max_retries - 1:
                            await asyncio.sleep(1)

            except TimeoutError:
                last_error = "Timeout"
                logger.warning(f"Intento {attempt + 1}: Timeout")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Intento {attempt + 1}: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(1)

        # Todos los intentos fallaron
        elapsed = time.monotonic() - start
        logger.error(f"[OLLAMA] Todos los intentos fallaron: {last_error}")
        return OllamaSearchResult(
            query=query,
            response="",
            elapsed=elapsed,
            source="ollama_direct",
            success=False,
            error=last_error,
            model=model_to_use,
        )

    async def batch_search(
        self,
        queries: list[str],
        concurrency: int = 4,
        model: str | None = None,
        max_tokens: int = 2000,
    ) -> list[OllamaSearchResult]:
        """
        Ejecuta múltiples búsquedas en paralelo.

        Args:
            queries: Lista de queries
            concurrency: Número de búsquedas simultáneas
            model: Modelo a usar
            max_tokens: Máximo de tokens por respuesta

        Returns:
            Lista de OllamaSearchResult
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def search_with_limit(query: str) -> OllamaSearchResult:
            async with semaphore:
                return await self.search(query, model, max_tokens)

        results = await asyncio.gather(
            *[search_with_limit(q) for q in queries], return_exceptions=True
        )

        # Procesar excepciones
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    OllamaSearchResult(
                        query=queries[i],
                        response="",
                        elapsed=0,
                        source="ollama_direct",
                        success=False,
                        error=str(result),
                        model=model or self.model,
                    )
                )
            else:
                processed_results.append(result)

        return processed_results

    async def list_models(self) -> list[dict[str, Any]]:
        """
        Lista modelos disponibles en Ollama.

        Returns:
            Lista de modelos
        """
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5))
            async with self.session.get(f"{self.base_url}/api/tags") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("models", [])
        except Exception as e:
            logger.warning(f"Error listando modelos: {e}")
        return []


# Singleton
_client_instance: OllamaN3Client | None = None


def get_ollama_n3_client() -> OllamaN3Client:
    """Obtener singleton del cliente Ollama N3."""
    global _client_instance
    if _client_instance is None:
        _client_instance = OllamaN3Client()
    return _client_instance


def reset_ollama_n3_client() -> None:
    """Resetear singleton (útil tras cambiar configuración)."""
    global _client_instance
    _client_instance = None


if __name__ == "__main__":
    # Test del cliente
    async def test():
        async with OllamaN3Client() as client:
            health = await client.health_check()
            print(f"Health check: {health}")

            if health:
                models = await client.list_models()
                print(f"Modelos disponibles: {len(models)}")
                for m in models[:3]:
                    print(f"  - {m.get('name')}")

                result = await client.search("Define brevemente qué es un agente cognitivo")
                print(f"\nResultado: {result.success}")
                print(f"Tiempo: {result.elapsed:.2f}s")
                print(f"Tokens: {result.tokens}")
                print(f"Respuesta: {result.response[:200]}...")

    asyncio.run(test())
