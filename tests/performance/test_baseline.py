"""Smoke de rendimiento: latencias de los endpoints críticos < 5s.

Mide con TestClient (sin red) sobre los routers reales con provider fake.
Umbral generoso de 5s para no flakear en CI cargado; cualquier regresión
de orden de magnitud (p.ej. bloqueo de I/O en el hot path) lo dispara.

Marcador: ``performance`` — excluible con ``-m "not performance"``.
"""

from __future__ import annotations

import time
from typing import Any

import pytest

UMBRAL_SEGUNDOS = 5.0


def _medir(client: Any, metodo: str, ruta: str, json: dict | None = None) -> float:
    t0 = time.monotonic()
    r = client.get(ruta) if metodo == "GET" else client.post(ruta, json=json or {})
    t1 = time.monotonic()
    assert r.status_code in (200, 201), f"{metodo} {ruta} -> {r.status_code}: {r.text[:200]}"
    return t1 - t0


@pytest.mark.performance
def test_baseline_health(mochila_client: Any) -> None:
    latencia = _medir(mochila_client, "GET", "/health")
    assert latencia < UMBRAL_SEGUNDOS, f"/health tardó {latencia:.2f}s"


@pytest.mark.performance
def test_baseline_models(mochila_client: Any) -> None:
    latencia = _medir(mochila_client, "GET", "/v1/models")
    assert latencia < UMBRAL_SEGUNDOS, f"/v1/models tardó {latencia:.2f}s"


@pytest.mark.performance
def test_baseline_status(mochila_client: Any) -> None:
    latencia = _medir(mochila_client, "GET", "/status")
    assert latencia < UMBRAL_SEGUNDOS, f"/status tardó {latencia:.2f}s"


@pytest.mark.performance
def test_baseline_metrics(mochila_client: Any) -> None:
    latencia = _medir(mochila_client, "GET", "/metrics")
    assert latencia < UMBRAL_SEGUNDOS, f"/metrics tardó {latencia:.2f}s"


@pytest.mark.performance
def test_baseline_chat_completions(mochila_client: Any) -> None:
    payload = {
        "model": "fake/pepe",
        "messages": [{"role": "user", "content": "rendimiento"}],
        "max_tokens": 32,
    }
    latencia = _medir(mochila_client, "POST", "/v1/chat/completions", payload)
    assert latencia < UMBRAL_SEGUNDOS, f"/v1/chat/completions tardó {latencia:.2f}s"


@pytest.mark.performance
def test_baseline_chat_stream(mochila_client: Any) -> None:
    payload = {
        "model": "fake/pepe",
        "messages": [{"role": "user", "content": "stream"}],
        "stream": True,
    }
    t0 = time.monotonic()
    r = mochila_client.post("/v1/chat/completions", json=payload)
    t1 = time.monotonic()
    assert r.status_code == 200
    assert "data:" in r.text
    assert t1 - t0 < UMBRAL_SEGUNDOS, f"stream tardó {t1 - t0:.2f}s"


@pytest.mark.performance
def test_baseline_20_chats_rapidos(mochila_client: Any) -> None:
    """20 peticiones de chat seguidas no deben degradar el hot path."""
    payload = {
        "model": "fake/pepe",
        "messages": [{"role": "user", "content": "x"}],
    }
    t0 = time.monotonic()
    for _ in range(20):
        r = mochila_client.post("/v1/chat/completions", json=payload)
        assert r.status_code == 200
    t1 = time.monotonic()
    total = t1 - t0
    assert total < UMBRAL_SEGUNDOS * 4, f"20 chats tardaron {total:.2f}s"
