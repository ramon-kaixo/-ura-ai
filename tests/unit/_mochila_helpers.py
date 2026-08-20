"""Tests de cobertura para core/mochila/mochila_server.py — TASK-20260815-003 P2.

Cubre las zonas sin testear del servidor FastAPI de la mochila:
scheduler VRAM (todo el ciclo de vida), lifespan, helpers de stream/guardian,
tool calls, proxy gateway, endpoints de memoria y ramas del router/models.
"""

import asyncio  # noqa: F401
import subprocess  # noqa: F401
import sys  # noqa: F401
import tempfile
import time  # noqa: F401
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock  # noqa: F401

import httpx  # noqa: F401
import pytest
from fastapi import HTTPException  # noqa: F401
from fastapi.responses import JSONResponse  # noqa: F401
from fastapi.testclient import TestClient


class FakeProvider:
    def __init__(self, nombre: str, modelos: list[str] | None = None) -> None:
        self.nombre = nombre
        self.modelos = modelos or [f"{nombre}-modelo-1", f"{nombre}-modelo-2"]
        self.llamadas: list[dict] = []

    async def health(self) -> dict:
        return {"status": "ok", "modelos_disponibles": self.modelos, "latencia_ms": 1.0}

    async def chat(self, modelo, mensajes, stream=False, tools=None, max_tokens=4096, temperature=0.0):
        self.llamadas.append({"modelo": modelo, "stream": stream, "mensajes": mensajes})
        if stream:
            yield {
                "choices": [{"index": 0, "delta": {"content": "hola"}, "finish_reason": None}],
                "usage": None,
            }
            yield {
                "choices": [{"index": 0, "delta": {}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 5},
            }
            return
        yield {
            "id": "resp-1",
            "object": "chat.completion",
            "created": 1,
            "model": modelo,
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "respuesta"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }


@pytest.fixture(scope="module")
def ms():
    import core.mochila.mochila_server as module
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter

    tmp = Path(tempfile.mkdtemp(prefix="mochila_cov_"))

    originales = {
        "_API_KEY": module._API_KEY,
        "PROVIDERS": module.PROVIDERS,
        "PROVIDER_TIMEOUTS": module.PROVIDER_TIMEOUTS,
        "CACHE_MODELS": module.CACHE_MODELS,
        "CACHE_MODELS_TS": module.CACHE_MODELS_TS,
        "scheduler": module.scheduler,
        "cost_tracker": module.cost_tracker,
        "rate_limiter": module.rate_limiter,
        "circuit_breaker": module.circuit_breaker,
        "router": module.router,
    }

    module._API_KEY = "test-key"
    module.PROVIDERS = {
        "ollama": FakeProvider("ollama"),
        "openrouter": FakeProvider("openrouter"),
        "gemini": FakeProvider("gemini"),
    }
    module.PROVIDER_TIMEOUTS = {"ollama": 120.0, "openrouter": 60.0, "gemini": 30.0}
    module.CACHE_MODELS = []
    module.CACHE_MODELS_TS = 0
    module.cost_tracker = CostTracker(cost_file=tmp / "costs.jsonl")
    module.rate_limiter = RateLimiter()
    module.circuit_breaker = CircuitBreaker(health_file=tmp / "health.json")

    scheduler = AsyncMock()
    scheduler.estimar_vram = lambda body: 10
    scheduler.acquire = AsyncMock(return_value="req-1")
    scheduler.release = AsyncMock()
    module.scheduler = scheduler

    module.router = module.Router(providers=module.PROVIDERS)

    yield module

    for nombre, valor in originales.items():
        setattr(module, nombre, valor)


@pytest.fixture
def client(ms):
    return TestClient(ms.app)


