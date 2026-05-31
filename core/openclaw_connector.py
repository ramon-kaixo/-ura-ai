#!/usr/bin/env python3
"""
Conector URA ↔ OpenClaw para entrenamiento N3.

Comunica con OpenClaw usando la CLI: openclaw agent --local --message "..." --json
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from core.guardian_openclaw import get_guardian

logger = logging.getLogger("openclaw_connector")

# Configuración por defecto
DEFAULT_TIMEOUT = 300  # 300 segundos para tareas autónomas (aumentado para OpenClaw lento)
MAX_RETRIES = 3


@dataclass
class SearchResult:
    """Resultado de búsqueda OpenClaw."""

    query: str
    response: str
    elapsed: float
    source: str
    success: bool
    error: str | None = None
    tokens: int = 0


class OpenClawConnector:
    """Cliente async para comunicar con OpenClaw vía CLI."""

    def __init__(self, timeout: int = DEFAULT_TIMEOUT, max_retries: int = MAX_RETRIES):
        self.timeout = timeout
        self.max_retries = max_retries

    async def __aenter__(self):
        """Context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""

    async def health_check(self) -> bool:
        """
        Verifica si OpenClaw está respondiendo vía CLI.

        Returns:
            True si healthy, False si no.
        """
        try:
            result = await asyncio.create_subprocess_exec(
                "openclaw",
                "agent",
                "--local",
                "--message",
                "responde OK",
                "--json",
                "--timeout",
                "30",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=35)

            if result.returncode == 0:
                try:
                    data = json.loads(stdout.decode())
                    return data.get("success", False)
                except json.JSONDecodeError:
                    return "OK" in stdout.decode()
            return False
        except Exception as e:
            logger.warning(f"Health check CLI falló: {e}")
            return False


async def execute(self, task: str, context: dict | None = None) -> dict[str, Any]:
    """
    Ejecuta tarea en OpenClaw usando CLI con protección del Guardián.

    Args:
        task: Tarea a ejecutar
        context: Contexto adicional (opcional)

    Returns:
        Dict con {'success': bool, 'response': str, 'error': str | None}
    """
    start = time.monotonic()

    try:
        guardian_result = await check_guardian(task, context)
        if not guardian_result["success"]:
            logger.warning(f"Guardián bloqueó la acción: {guardian_result.get('message')}")
            return {
                "success": False,
                "response": "",
                "error": f"Guardián bloqueó: {guardian_result.get('message')}",
                "elapsed": time.monotonic() - start,
                "guardian_bloqueado": True,
            }

        cmd = build_command(task)
        result = await run_subprocess(cmd)

        stdout, stderr = await asyncio.wait_for(result.communicate(), timeout=self.timeout + 5)
        elapsed = time.monotonic() - start

        if result.returncode == 0:
            try:
                data = json.loads(stdout.decode())
                response_text = extract_response(data)
                if data.get("aborted", False):
                    return {
                        "success": False,
                        "response": response_text,
                        "error": "Operación abortada por timeout",
                        "elapsed": elapsed,
                    }
                return {
                    "success": True,
                    "response": response_text,
                    "error": None,
                    "elapsed": elapsed,
                    "guardian_aprobado": True,
                }
            except json.JSONDecodeError:
                return {
                    "success": True,
                    "response": stdout.decode(),
                    "error": None,
                    "elapsed": elapsed,
                    "guardian_aprobado": True,
                }
        else:
            error_msg = stderr.decode() if stderr else f"Exit code {result.returncode}"
            return {"success": False, "response": "", "error": error_msg, "elapsed": elapsed}

    except TimeoutError:
        elapsed = time.monotonic() - start
        return {
            "success": False,
            "response": "",
            "error": f"Timeout después de {self.timeout}s",
            "elapsed": elapsed,
        }
    except Exception as e:
        elapsed = time.monotonic() - start
        logger.error(f"Error ejecutando OpenClaw CLI: {e}")
        return {"success": False, "response": "", "error": str(e), "elapsed": elapsed}


async def check_guardian(task: str, context: dict | None) -> dict[str, Any]:
    guardian = get_guardian()
    return await guardian.ejecutar(task, context=context or {})


def build_command(task: str) -> List[str]:
    return [
        "openclaw",
        "agent",
        "--local",
        "--agent",
        "main",
        "--message",
        task,
        "--json",
        "--timeout",
        str(self.timeout),
    ]


async def run_subprocess(cmd: List[str]) -> asyncio.subprocess.Process:
    result = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    return result


def extract_response(data: dict) -> str:
    response_text = get_first_payload_text(data)
    return response_text


def get_first_payload_text(data: dict) -> str:
    if "payloads" in data and data["payloads"]:
        return data["payloads"][0].get("text", "")
    elif "response" in data:
        response_text = data.get("response", "")
    else:
        response_text = ""
    return response_text

    async def search(self, query: str, max_tokens: int = 2000) -> SearchResult:
        """
        Ejecuta búsqueda en OpenClaw usando CLI.

        Args:
            query: Query de búsqueda
            max_tokens: Máximo de tokens (para validación)

        Returns:
            SearchResult con respuesta
        """
        start = time.monotonic()

        try:
            # Usar execute para búsqueda
            result = await self.execute(query)

            elapsed = time.monotonic() - start

            return SearchResult(
                query=query,
                response=result.get("response", ""),
                elapsed=elapsed,
                source="openclaw",
                success=result.get("success", False),
                error=result.get("error"),
            )

        except Exception as e:
            elapsed = time.monotonic() - start
            logger.error(f"Error en búsqueda OpenClaw: {e}")
            return SearchResult(
                query=query,
                response="",
                elapsed=elapsed,
                source="openclaw",
                success=False,
                error=str(e),
            )

    def _extract_response_text(self, data: dict[str, Any]) -> str:
        """Extrae texto de respuesta de OpenClaw."""
        # OpenClaw puede devolver respuesta en diferentes formatos
        if "response" in data:
            return str(data["response"])
        elif "resultados" in data and data["resultados"]:
            # Si hay resultados, concatenar snippets
            snippets = [r.get("snippet", "") for r in data["resultados"]]
            return " ".join(snippets)
        elif "razonamiento" in data:
            return str(data["razonamiento"])
        elif "text" in data:
            return str(data["text"])
        else:
            return str(data)

    async def batch_search(
        self, queries: list[str], concurrency: int = 4, max_tokens: int = 2000
    ) -> list[SearchResult]:
        """
        Ejecuta múltiples búsquedas en paralelo.

        Args:
            queries: Lista de queries
            concurrency: Número de búsquedas simultáneas
            max_tokens: Máximo de tokens por respuesta

        Returns:
            Lista de SearchResult
        """
        semaphore = asyncio.Semaphore(concurrency)

        async def search_with_limit(query: str) -> SearchResult:
            async with semaphore:
                return await self.search(query, max_tokens)

        results = await asyncio.gather(
            *[search_with_limit(q) for q in queries], return_exceptions=True
        )

        # Procesar excepciones
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                processed_results.append(
                    SearchResult(
                        query=queries[i],
                        response="",
                        elapsed=0,
                        source="openclaw",
                        success=False,
                        error=str(result),
                    )
                )
            else:
                processed_results.append(result)

        return processed_results


# Singleton
_connector_instance: OpenClawConnector | None = None


def get_openclaw_connector() -> OpenClawConnector:
    """Obtener singleton del conector."""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = OpenClawConnector()
    return _connector_instance


def reset_openclaw_connector() -> None:
    """Resetear singleton (útil tras cambiar configuración)."""
    global _connector_instance
    _connector_instance = None


if __name__ == "__main__":
    # Test del conector
    async def test():
        async with OpenClawConnector() as connector:
            health = await connector.health_check()
            print(f"Health check: {health}")

            if health:
                result = await connector.search("test query")
                print(f"Resultado: {result}")

    asyncio.run(test())
