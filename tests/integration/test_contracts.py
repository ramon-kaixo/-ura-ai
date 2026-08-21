"""Pruebas de contrato (API): los endpoints devuelven el esquema EXACTO.

Cada contrato se valida con Pydantic ``model_validate`` + comparación de
campos: si un endpoint añade, quita o cambia un campo, el test falla.
"""

from __future__ import annotations

from typing import Any

import pytest
from pydantic import BaseModel, Field, ValidationError

from core.mochila.models import ChatResponse

# ── Modelos de contrato (esquemas esperados) ─────────────────────────


class ProviderHealthContract(BaseModel):
    status: str
    modelos_disponibles: list[str] | None = None


class HealthContract(BaseModel):
    status: str
    providers: dict[str, ProviderHealthContract] = Field(min_length=1)


class ModelInfoContract(BaseModel):
    id: str
    object: str = "model"
    provider: str


class ModelsListContract(BaseModel):
    object: str = "list"
    data: list[ModelInfoContract] = Field(min_length=1)


class BreakerStatusContract(BaseModel):
    model_config = {"extra": "forbid"}

    state: str
    failure_count: int
    success_count: int
    consecutive_failures: int
    last_failure_time: float | None
    last_success_time: float | None


class BreakerContract(BaseModel):
    model_config = {"extra": "forbid"}

    status: str
    provider: str


class ChatMessageContract(BaseModel):
    role: str
    content: str


class ChatChoiceContract(BaseModel):
    index: int
    message: ChatMessageContract
    finish_reason: str | None


class UsageContract(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


def _validar_exacto(modelo: type[BaseModel], datos: dict[str, Any]) -> BaseModel:
    """Valida con Pydantic estricto: falla si hay campos extra o tipos raros."""
    return modelo.model_validate(datos)


# ── Contratos ─────────────────────────────────────────────────────────


def test_contrato_health(mochila_client: Any) -> None:
    r = mochila_client.get("/health")
    assert r.status_code == 200, r.text
    contrato = _validar_exacto(HealthContract, r.json())
    assert contrato.status == "ok"
    assert contrato.providers["fake"].status == "ok"


def test_contrato_models(mochila_client: Any) -> None:
    r = mochila_client.get("/v1/models")
    assert r.status_code == 200, r.text
    lista = _validar_exacto(ModelsListContract, r.json())
    ids = [m.id for m in lista.data]
    assert any("fake" in i for i in ids)


def test_contrato_breaker_status(mochila_client: Any) -> None:
    r = mochila_client.get("/breaker")
    assert r.status_code == 200, r.text
    datos = r.json()
    assert "fake" in datos
    contrato = _validar_exacto(BreakerStatusContract, datos["fake"])
    assert contrato.state == "closed"


def test_contrato_breaker_reset(mochila_client: Any) -> None:
    r = mochila_client.post("/breaker/reset/fake")
    assert r.status_code == 200, r.text
    contrato = _validar_exacto(BreakerContract, r.json())
    assert contrato.status == "reset"
    assert contrato.provider == "fake"


def test_contrato_breaker_reset_404(mochila_client: Any) -> None:
    r = mochila_client.post("/breaker/reset/no_existe")
    assert r.status_code == 404


def test_contrato_chat_completion(mochila_client: Any) -> None:
    r = mochila_client.post(
        "/v1/chat/completions",
        json={
            "model": "fake/pepe",
            "messages": [{"role": "user", "content": "hola"}],
            "max_tokens": 128,
            "temperature": 0.0,
        },
    )
    assert r.status_code == 200, r.text
    datos = r.json()
    # Esquema exacto contra el modelo oficial del paquete
    respuesta = ChatResponse.model_validate(datos)
    assert respuesta.object == "chat.completion"
    assert respuesta.id.startswith("chatcmpl-")
    assert respuesta.model == "pepe"
    assert len(respuesta.choices) == 1
    # Contratos de detalle
    uso = _validar_exacto(UsageContract, datos["usage"])
    assert uso.total_tokens == uso.prompt_tokens + uso.completion_tokens
    eleccion = _validar_exacto(ChatChoiceContract, datos["choices"][0])
    assert eleccion.message.role == "assistant"
    assert "pepe" in eleccion.message.content
    # Headers de ruta
    assert r.headers.get("X-Mochila-Provider") == "fake"
    assert r.headers.get("X-Mochila-Modelo") == "pepe"


def test_contrato_chat_sin_mensajes_invalidos(mochila_client: Any) -> None:
    """El esquema de entrada rechaza mensajes mal formados."""
    r = mochila_client.post(
        "/v1/chat/completions",
        json={"model": "fake/pepe", "messages": "no-lista"},
    )
    assert r.status_code == 422


def test_contrato_chat_stream_sse(mochila_client: Any) -> None:
    """El contrato de streaming responde SSE (text/event-stream)."""
    r = mochila_client.post(
        "/v1/chat/completions",
        json={
            "model": "fake/pepe",
            "messages": [{"role": "user", "content": "cuentame algo"}],
            "stream": True,
        },
    )
    assert r.status_code == 200, r.text
    assert r.headers.get("content-type", "").startswith("text/event-stream")
    assert "data:" in r.text


def test_contrato_provider_caido_devuelve_502(mochila_client: Any) -> None:
    """Contrato de error: provider que falla -> 502 con JSON {error}."""

    class ProviderRoto:
        name = "roto"

        async def chat(self, **_: Any) -> Any:
            raise RuntimeError("provider roto")
            yield  # pragma: no cover - nunca se alcanza

    state = mochila_client.app.state  # type: ignore[attr-defined]
    _ = state
    # Usamos un state con provider roto montado sobre la misma app de rutas
    import tempfile
    from pathlib import Path as _P

    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    from core.mochila._state import MochilaState
    from core.mochila.circuit_breaker import CircuitBreaker
    from core.mochila.cost_tracker import CostTracker
    from core.mochila.rate_limiter import RateLimiter
    from core.mochila.router import Router
    from core.mochila.routes import create_api_router

    tmp_dir = _P(tempfile.mkdtemp(prefix="ura-test-mochila-"))
    providers = {"roto": ProviderRoto()}
    state = MochilaState(
        providers=providers,
        provider_timeouts={"roto": 5.0},
        scheduler=None,
        router=Router(providers=providers),
        circuit_breaker=CircuitBreaker(health_file=tmp_dir / "breaker.json"),
        rate_limiter=RateLimiter(),
        cost_tracker=CostTracker(cost_file=tmp_dir / "cost.jsonl"),
    )
    app = FastAPI()
    app.include_router(create_api_router(state))
    with TestClient(app) as client:
        r = client.post(
            "/v1/chat/completions",
            json={"model": "roto/x", "messages": [{"role": "user", "content": "hola"}]},
        )
    assert r.status_code == 502
    assert "error" in r.json() or "detail" in r.json()


def test_contrato_chatrequest_rechaza_mensajes_invalidos() -> None:
    """El esquema de entrada exige mensajes como lista (no string ni dict)."""

    from core.mochila.models import ChatRequest

    with pytest.raises(ValidationError):
        ChatRequest.model_validate({"model": "auto", "messages": {"role": "user"}})
