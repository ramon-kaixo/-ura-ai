"""Fixtures compartidos de integración: estado de la Mochila con providers fake.

Permite levantar la API de la Mochila (routers reales) sin Ollama ni red:
el provider ``fake`` devuelve respuestas OpenAI-compatibles deterministas.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest


class FakeProvider:
    """Provider de chat determinista para tests de contrato/E2E/rendimiento."""

    name = "fake"

    async def health(self) -> dict:
        return {"status": "ok", "modelos_disponibles": ["pepe-1b", "pepe-3b"]}

    async def chat(
        self,
        modelo: str,
        mensajes: list,
        stream: bool = False,
        tools: Any = None,
        max_tokens: int = 4096,
        temperature: float = 0.0,
    ) -> AsyncGenerator[dict, None]:
        contenido = f"respuesta fake para {modelo}"
        if tools:
            contenido += f" (tools={len(tools) if isinstance(tools, list) else 1})"
        yield {
            "id": "chatcmpl-fake-001",
            "object": "chat.completion",
            "created": 1_700_000_000,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": contenido},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }


@pytest.fixture(scope="module")
def mochila_fake_state() -> Any:
    """MochilaState con un único provider fake y componentes reales."""
    import tempfile
    from pathlib import Path

    from core.mochila._state import MochilaState
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter
    from core.mochila.router import Router

    tmp = Path(tempfile.mkdtemp(prefix="ura-test-mochila-"))
    providers = {"fake": FakeProvider()}
    state = MochilaState(
        providers=providers,
        provider_timeouts={"fake": 30.0},
        scheduler=None,
        router=Router(providers=providers),
        circuit_breaker=CircuitBreaker(health_file=tmp / "breaker.json"),
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(cost_file=tmp / "cost.jsonl"),
    )
    return state


@pytest.fixture()
def mochila_client(mochila_fake_state: Any):
    """TestClient sobre los routers reales de la Mochila con state fake."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.mochila.routes import create_api_router

    app = FastAPI()
    app.include_router(create_api_router(mochila_fake_state))
    with TestClient(app) as client:
        yield client
