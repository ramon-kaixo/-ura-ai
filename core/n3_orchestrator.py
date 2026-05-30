#!/usr/bin/env python3
"""
Orquestador N3 dual - Ollama directo + OpenClaw complementario.

Detecta automáticamente qué N3 está disponible y rutea tareas
al backend apropiado según el tipo de tarea.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger("n3_orchestrator")

# Módulos de seguridad (Paso 2B)
from core.security.input_sanitizer import sanitize_user_input
from core.security.jailbreak_guard import detect_jailbreak_attempt


class N3Orchestrator:
    """Orquestador N3 dual con routing automático."""

    def __init__(
        self,
        openclaw_url: str = "http://localhost:18789",
        ollama_url: str = "http://127.0.0.1:11434",
    ):
        """
        Inicializa el orquestador N3 dual.

        Args:
            openclaw_url: URL de OpenClaw (si está disponible)
            ollama_url: URL de Ollama directo
        """
        self.openclaw_url = openclaw_url
        self.ollama_url = ollama_url
        self.openclaw_available = False

    async def _check_openclaw_available(self) -> bool:
        """Verifica si OpenClaw está disponible."""
        try:
            from core.openclaw_health import check_openclaw_ready

            return await check_openclaw_ready(self.openclaw_url, timeout=5, max_retries=2)
        except Exception as e:
            logger.warning(f"Error verificando OpenClaw: {e}")
            return False

    async def _ensure_openclaw_checked(self):
        """Asegura que se ha verificado la disponibilidad de OpenClaw."""
        if not hasattr(self, "_openclaw_checked"):
            self.openclaw_available = await self._check_openclaw_available()
            self._openclaw_checked = True
            logger.info(f"[N3_ORCHESTRATOR] OpenClaw disponible: {self.openclaw_available}")

    async def route_task(
        self, task_type: str, query: str, context: dict | None = None
    ) -> dict[str, Any]:
        """
        Rutea tarea al backend apropiado según tipo.

        Args:
            task_type: Tipo de tarea ('system', 'file_ops', 'multi_step', 'search', 'qa', 'decompose')
            query: Query o tarea a ejecutar
            context: Contexto adicional (opcional)

        Returns:
            Dict con {'success': bool, 'response': str, 'error': str | None, 'backend': str}
        """
        await self._ensure_openclaw_checked()

        # Tareas autónomas → OpenClaw si disponible, sino Ollama (fallback)
        if task_type in ("system", "file_ops", "multi_step"):
            if self.openclaw_available:
                logger.info(f"[N3_ORCHESTRATOR] Ruteando a OpenClaw: {task_type}")
                return await self._execute_openclaw(query, context)
            else:
                logger.warning(
                    f"[N3_ORCHESTRATOR] OpenClaw no disponible, usando Ollama fallback para: {task_type}"
                )
                return await self._execute_ollama(query, context)
        # Consultas rápidas → siempre Ollama directo
        else:
            logger.info(f"[N3_ORCHESTRATOR] Ruteando a Ollama directo: {task_type}")
            return await self._execute_ollama(query, context)

    async def _execute_openclaw(self, task: str, context: dict | None = None) -> dict[str, Any]:
        """Ejecuta tarea en OpenClaw usando CLI."""
        try:
            from core.openclaw_connector import OpenClawConnector

            async with OpenClawConnector(timeout=120) as connector:
                result = await connector.execute(task, context)

            return {
                "success": result["success"],
                "response": result["response"],
                "error": result["error"],
                "backend": "openclaw",
                "elapsed": result.get("elapsed", 0),
            }
        except Exception as e:
            logger.error(f"[N3_ORCHESTRATOR] Error ejecutando en OpenClaw: {e}")
            # Fallback a Ollama si OpenClaw falla
            logger.warning("[N3_ORCHESTRATOR] Fallback a Ollama tras error en OpenClaw")
            return await self._execute_ollama(task, context)

    async def _execute_ollama(self, query: str, context: dict | None = None) -> dict[str, Any]:
        """Ejecuta consulta en Ollama directo."""
        try:
            from core.ollama_n3_client import OllamaN3Client

            # Construir prompt con contexto si existe
            prompt = query
            if context:
                prompt = f"Contexto: {context}\n\nPregunta: {query}"

            async with OllamaN3Client(base_url=self.ollama_url, timeout=60) as client:
                result = await client.search(query=prompt, max_tokens=2000)

            return {
                "success": result.success,
                "response": result.response,
                "error": result.error,
                "backend": "ollama_direct",
                "elapsed": result.elapsed,
                "tokens": result.tokens,
            }
        except Exception as e:
            logger.error(f"[N3_ORCHESTRATOR] Error ejecutando en Ollama: {e}")
            return {
                "success": False,
                "response": "",
                "error": str(e),
                "backend": "ollama_direct",
                "elapsed": 0,
            }

    async def search(self, query: str) -> dict[str, Any]:
        """
        Búsqueda rápida usando Ollama directo.

        Args:
            query: Query de búsqueda

        Returns:
            Dict con resultado
        """
        # Paso 2B: Sanitizar query
        query = sanitize_user_input(query)

        # Paso 2B: Detectar jailbreak
        if detect_jailbreak_attempt(query):
            logger.warning(f"Jailbreak attempt detectado en search: {query[:50]}...")
            return {"error": "Query bloqueado por seguridad (jailbreak attempt)"}

        return await self.route_task("search", query)

    async def qa(self, question: str, context: str | None = None) -> dict[str, Any]:
        """
        Pregunta-respuesta usando Ollama directo.

        Args:
            question: Pregunta
            context: Contexto opcional

        Returns:
            Dict con resultado
        """
        # Paso 2B: Sanitizar inputs
        question = sanitize_user_input(question)
        if context:
            context = sanitize_user_input(context)

        # Paso 2B: Detectar jailbreak
        if detect_jailbreak_attempt(question):
            logger.warning(f"Jailbreak attempt detectado en qa: {question[:50]}...")
            return {"error": "Pregunta bloqueada por seguridad (jailbreak attempt)"}

        ctx = {"context": context} if context else None
        return await self.route_task("qa", question, ctx)

    async def decompose(self, topic: str) -> dict[str, Any]:
        """
        Descomposición de tema usando Ollama directo.

        Args:
            topic: Tema a descomponer

        Returns:
            Dict con resultado
        """
        return await self.route_task("decompose", topic)

    async def system_task(self, task: str) -> dict[str, Any]:
        """
        Tarea de sistema usando OpenClaw (si disponible) o Ollama fallback.

        Args:
            task: Tarea de sistema

        Returns:
            Dict con resultado
        """
        return await self.route_task("system", task)


# Singleton
_orchestrator_instance: N3Orchestrator | None = None


def get_n3_orchestrator() -> N3Orchestrator:
    """Obtener singleton del orquestador N3."""
    global _orchestrator_instance
    if _orchestrator_instance is None:
        _orchestrator_instance = N3Orchestrator()
    return _orchestrator_instance


def reset_n3_orchestrator() -> None:
    """Resetear singleton."""
    global _orchestrator_instance
    _orchestrator_instance = None


if __name__ == "__main__":
    # Test del orquestador
    async def test():
        logging.basicConfig(level=logging.INFO)
        orchestrator = N3Orchestrator()

        # Test búsqueda (Ollama directo)
        result = await orchestrator.search("¿Qué es un agente cognitivo?")
        print(f"Search result: {result['success']}, backend: {result['backend']}")

        # Test tarea de sistema (OpenClaw si disponible)
        result = await orchestrator.system_task("Lista archivos en /tmp/")
        print(f"System task result: {result['success']}, backend: {result['backend']}")

    asyncio.run(test())
