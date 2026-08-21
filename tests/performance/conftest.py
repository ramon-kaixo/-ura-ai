"""Fixtures para tests/performance: mismos fakes que tests/integration.

Se reutiliza el patrón del conftest de integración (provider fake + state
real) para que el baseline de rendimiento mida los routers reales.
"""

from __future__ import annotations

import tempfile
from collections.abc import AsyncGenerator
from pathlib import Path
from typing import Any

import pytest


class _FakeProvider:
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
        yield {
            "id": "chatcmpl-fake-001",
            "object": "chat.completion",
            "created": 1_700_000_000,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": f"respuesta fake para {modelo}"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 12, "completion_tokens": 4, "total_tokens": 16},
        }


@pytest.fixture(scope="module")
def mochila_client() -> Any:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.mochila._state import MochilaState
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter
    from core.mochila.router import Router
    from core.mochila.routes import create_api_router

    tmp = Path(tempfile.mkdtemp(prefix="ura-test-perf-"))
    providers = {"fake": _FakeProvider()}
    state = MochilaState(
        providers=providers,
        provider_timeouts={"fake": 30.0},
        scheduler=None,
        router=Router(providers=providers),
        circuit_breaker=CircuitBreaker(health_file=tmp / "breaker.json"),
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(cost_file=tmp / "cost.jsonl"),
    )
    app = FastAPI()
    app.include_router(create_api_router(state))
    with TestClient(app) as client:
        yield client
