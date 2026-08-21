"""Pruebas End-to-End: servidor real (uvicorn) en puerto de pruebas.

Levanta la API de la Mochila con los routers reales y un provider fake,
hace peticiones HTTP reales por socket y valida que el sistema responde
y no se cae entre peticiones.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Generator
from typing import Any

import httpx
import pytest

from core.mochila.models import ChatResponse


def _puerto_libre() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="module")
def e2e_server(mochila_fake_state: Any) -> Generator[str, None, None]:
    """Arranca uvicorn en un puerto libre y devuelve la base URL."""
    import uvicorn
    from fastapi import FastAPI

    from core.mochila.routes import create_api_router

    app = FastAPI()
    app.include_router(create_api_router(mochila_fake_state))
    puerto = _puerto_libre()
    config = uvicorn.Config(app, host="127.0.0.1", port=puerto, log_level="warning")
    server = uvicorn.Server(config)
    hilo = threading.Thread(target=server.run, daemon=True)
    hilo.start()

    base = f"http://127.0.0.1:{puerto}"
    # Esperar a que el servidor acepte conexiones (máx 15s)
    for _ in range(150):
        try:
            with httpx.Client(timeout=1.0) as c:
                c.get(f"{base}/health")
            break
        except Exception:
            time.sleep(0.1)
    else:
        server.should_exit = True
        pytest.fail("El servidor de pruebas no arrancó en 15s")

    yield base

    server.should_exit = True
    hilo.join(timeout=10)


def test_e2e_health_servidor_real(e2e_server: str) -> None:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{e2e_server}/health")
    assert r.status_code == 200
    datos = r.json()
    assert datos["status"] == "ok"
    assert "fake" in datos["providers"]


def test_e2e_chat_completions_servidor_real(e2e_server: str) -> None:
    payload = {
        "model": "fake/pepe",
        "messages": [{"role": "user", "content": "hola e2e"}],
        "max_tokens": 64,
        "temperature": 0.0,
    }
    with httpx.Client(timeout=15.0) as client:
        r = client.post(f"{e2e_server}/v1/chat/completions", json=payload)
    assert r.status_code == 200, r.text
    datos = r.json()
    respuesta = ChatResponse.model_validate(datos)
    assert respuesta.object == "chat.completion"
    assert respuesta.model == "pepe"
    assert respuesta.choices[0]["message"]["role"] == "assistant"
    assert "pepe" in respuesta.choices[0]["message"]["content"]
    assert r.headers.get("x-mochila-provider") == "fake"


def test_e2e_el_sistema_sigue_vivo_tras_peticiones(e2e_server: str) -> None:
    """Varias peticiones seguidas: el servidor no se cae."""
    with httpx.Client(timeout=10.0) as client:
        for i in range(5):
            r = client.get(f"{e2e_server}/health")
            assert r.status_code == 200
            r2 = client.post(
                f"{e2e_server}/v1/chat/completions",
                json={
                    "model": "fake/pepe",
                    "messages": [{"role": "user", "content": f"peticion {i}"}],
                },
            )
            assert r2.status_code == 200, f"falló en la petición {i}"
            assert ChatResponse.model_validate(r2.json()).id.startswith("chatcmpl-")


def test_e2e_modelos_servidor_real(e2e_server: str) -> None:
    with httpx.Client(timeout=10.0) as client:
        r = client.get(f"{e2e_server}/v1/models")
    assert r.status_code == 200
    datos = r.json()
    assert datos["object"] == "list"
    ids = [m["id"] for m in datos["data"]]
    assert "fake/pepe-1b" in ids
