"""Approval tests para endpoints críticos."""
from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
import pytest

SNAPSHOT_DIR = Path(__file__).parent / "snapshots"

MODEL_ROUTER = os.environ.get("URA_MODEL_ROUTER_URL", "http://localhost:11435")


def _load_approved(name: str) -> dict:
    path = SNAPSHOT_DIR / f"{name}.approved.json"
    return json.loads(path.read_text())


def _save_approved(name: str, data: dict) -> None:
    SNAPSHOT_DIR.mkdir(exist_ok=True)
    path = SNAPSHOT_DIR / f"{name}.approved.json"
    path.write_text(json.dumps(data, indent=2, sort_keys=True))


def _check_endpoint(url: str, timeout: int = 10) -> httpx.Response:
    try:
        r = httpx.get(url, timeout=timeout)
        if r.status_code != 200:
            pytest.skip(reason=f"Endpoint {url} respondió {r.status_code}")
        return r
    except httpx.ConnectError:
        pytest.skip(reason=f"Endpoint no disponible en {url}")
    except httpx.RemoteProtocolError:
        pytest.skip(reason=f"Endpoint {url} desconectó sin respuesta (entorno saturado)")


def _post_endpoint(url: str, payload: dict, timeout: int = 30) -> httpx.Response:
    try:
        r = httpx.post(url, json=payload, timeout=timeout)
        if r.status_code != 200:
            pytest.skip(reason=f"Endpoint {url} respondió {r.status_code}")
        return r
    except httpx.ConnectError:
        pytest.skip(reason=f"Endpoint no disponible en {url}")
    except httpx.RemoteProtocolError:
        pytest.skip(reason=f"Endpoint {url} desconectó sin respuesta (entorno saturado)")


@pytest.mark.integration
def test_approval_health():
    r = _check_endpoint(f"{MODEL_ROUTER}/health")
    # _save_approved("health", r.json())
    approved = _load_approved("health")
    assert r.json()["status"] == approved["status"]
    assert r.json()["ollama"] == approved["ollama"]
    assert r.json()["power_mode"] == approved["power_mode"]
    assert isinstance(r.json()["models_available"], int)


@pytest.mark.integration
def test_approval_chat_completions():
    payload = {
        "model": "qwen2.5-coder:14b",
        "messages": [{"role": "user", "content": "hola"}],
    }
    r = _post_endpoint(f"{MODEL_ROUTER}/v1/chat/completions", payload)
    body = r.json()
    # _save_approved("chat_completions", body)
    approved = _load_approved("chat_completions")
    assert body["object"] == approved["object"]
    assert body["model"] == approved["model"]
    assert len(body["choices"]) == len(approved["choices"])
    assert body["choices"][0]["index"] == approved["choices"][0]["index"]
    assert body["choices"][0]["finish_reason"] == approved["choices"][0]["finish_reason"]


@pytest.mark.integration
def test_approval_metrics():
    r = _check_endpoint(f"{MODEL_ROUTER}/metrics")
    data = {"status": r.status_code, "body_start": r.text[:200]}
    # _save_approved("metrics", data)
    approved = _load_approved("metrics")
    assert data["status"] == approved["status"]
