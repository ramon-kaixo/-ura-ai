"""Tests para sintetizador y analizador de memoria (LLM vía httpx mockeado)."""
from __future__ import annotations

import json
from unittest import mock

import pytest

from core.memoria.analizador import analizar
from core.memoria.sintetizador import sintetizar


class FakeCliente:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return False

    async def post(self, *a, **kw):
        return self._resp


class RespOk:
    is_error = False
    status_code = 200

    def __init__(self, content: str):
        self._content = content

    def json(self):
        return {"message": {"content": self._content}}

    def raise_for_status(self):
        return None


class RespError:
    is_error = True
    status_code = 503

    def json(self):
        return {}

    def raise_for_status(self):
        return None


@pytest.fixture(autouse=True)
def _patch_ollama_host(monkeypatch):
    monkeypatch.setenv("URA_OLLAMA_HOST", "127.0.0.1")
    monkeypatch.setenv("URA_OLLAMA_PORT", "11434")
    yield


# ============ SINTETIZADOR ============


@pytest.mark.asyncio
async def test_sintetizar_sin_ideas(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.sintetizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    out = await sintetizar("que es el SEO")
    assert out["total_ideas"] == 0
    assert "No tengo informacion en memoria" in out["informe"]
    assert out["fuentes"] == []


@pytest.mark.asyncio
async def test_sintetizar_con_ideas_ok(monkeypatch) -> None:
    ideas = [
        {"fuente": "fuente1", "tipo": "dato", "coste": "", "herramienta": "", "idea": "idea uno"},
        {"fuente": "fuente2", "tipo": "herramienta", "coste": "gratis", "herramienta": "Canva", "idea": "idea dos"},
        {"fuente": "", "tipo": "tecnica", "coste": "", "herramienta": "", "idea": "idea tres"},
    ]
    monkeypatch.setattr("core.memoria.sintetizador.buscar_ideas", mock.AsyncMock(return_value=ideas))
    monkeypatch.setattr(
        "core.memoria.sintetizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk("# Informe\nResumen ejecutivo")),
    )
    out = await sintetizar("peticion x")
    assert out["informe"].startswith("# Informe")
    assert out["total_ideas"] == 3
    assert sorted(out["fuentes"]) == ["fuente1", "fuente2"]


@pytest.mark.asyncio
async def test_sintetizar_error_http(monkeypatch) -> None:
    ideas = [{"fuente": "f", "tipo": "dato", "coste": "", "herramienta": "", "idea": "x"}]
    monkeypatch.setattr("core.memoria.sintetizador.buscar_ideas", mock.AsyncMock(return_value=ideas))
    monkeypatch.setattr(
        "core.memoria.sintetizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespError()),
    )
    out = await sintetizar("p")
    assert out["informe"] == "Error generando informe: HTTP 503"


@pytest.mark.asyncio
async def test_sintetizar_excepcion_cliente(monkeypatch) -> None:
    ideas = [{"fuente": "f", "tipo": "dato", "coste": "", "herramienta": "", "idea": "x"}]
    monkeypatch.setattr("core.memoria.sintetizador.buscar_ideas", mock.AsyncMock(return_value=ideas))

    class ClienteRota:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise ConnectionError("red caida")

    monkeypatch.setattr("core.memoria.sintetizador.httpx.AsyncClient", lambda *a, **k: ClienteRota())
    out = await sintetizar("p")
    assert out["informe"] == "Error generando informe: red caida"


@pytest.mark.asyncio
async def test_sintetizador_prompt_incluye_formato(monkeypatch) -> None:
    ideas = [{"fuente": "f", "tipo": "herramienta", "coste": "gratis", "herramienta": "Canva", "idea": "usa canva"}]
    monkeypatch.setattr("core.memoria.sintetizador.buscar_ideas", mock.AsyncMock(return_value=ideas))

    capturado: dict = {}

    class ClienteCaptura:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            capturado["json"] = json
            return RespOk("ok")

    monkeypatch.setattr("core.memoria.sintetizador.httpx.AsyncClient", lambda *a, **k: ClienteCaptura())
    await sintetizar("mi peticion")
    body = capturado["json"]
    assert body["model"] == "qwen2.5-coder:14b"
    assert "mi peticion" in body["messages"][0]["content"]
    assert "[herramienta (gratis) [Canva]]" in body["messages"][0]["content"]
    assert "fuente: f" in body["messages"][0]["content"]


# ============ ANALIZADOR ============


@pytest.mark.asyncio
async def test_analizar_sin_memoria_plan_json(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    plan = {"fases": ["saber", "hacer"], "tema_principal": "SEO", "palabras_clave": ["a"], "razon": "poca cobertura"}
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk(json.dumps(plan))),
    )
    out = await analizar("explica SEO para bares")
    assert out["fases"] == ["saber", "hacer"]
    assert out["tema_principal"] == "SEO"
    assert out["hay_memoria"] is False
    assert out["ideas_encontradas"] == 0
    assert out["razon"] == "poca cobertura"


@pytest.mark.asyncio
async def test_analizar_con_memoria_y_temas(monkeypatch) -> None:
    ideas = [{"tema": "SEO"}, {"tema": "SEO"}, {"tema": "local"}]
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=ideas))
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk('{"fases": ["comprar"]}')),
    )
    out = await analizar("p")
    assert out["hay_memoria"] is True
    assert out["ideas_encontradas"] == 3
    assert sorted(out["temas_cubiertos"]) == ["SEO", "local"]


@pytest.mark.asyncio
async def test_analizar_json_embebido(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    content = 'pensando... {"fases": ["saber"], "tema_principal": "T"} ...fin'
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk(content)),
    )
    out = await analizar("p")
    assert out["fases"] == ["saber"]
    assert out["tema_principal"] == "T"


@pytest.mark.asyncio
async def test_analizar_json_invalido_fallback(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk("sin json en absoluto")),
    )
    out = await analizar("mi pregunta")
    assert out["fases"] == ["saber", "hacer"]
    assert out["tema_principal"] == "mi pregunta"
    assert out["palabras_clave"] == ["mi pregunta"]


@pytest.mark.asyncio
async def test_analizar_error_http(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespError()),
    )
    out = await analizar("p")
    assert out == {"error": "Ollama 503", "peticion": "p"}


@pytest.mark.asyncio
async def test_analizar_excepcion_general(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))

    class ClienteRota:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            raise OSError("boom")

    monkeypatch.setattr("core.memoria.analizador.httpx.AsyncClient", lambda *a, **k: ClienteRota())
    out = await analizar("p")
    assert out["error"] == "boom"


@pytest.mark.asyncio
async def test_analizador_plan_defaults_con_palabras_clave(monkeypatch) -> None:
    monkeypatch.setattr("core.memoria.analizador.buscar_ideas", mock.AsyncMock(return_value=[]))
    monkeypatch.setattr(
        "core.memoria.analizador.httpx.AsyncClient",
        lambda *a, **k: FakeCliente(RespOk('{"fases": []}')),
    )
    out = await analizar("p")
    assert out["fases"] == []
    assert out["tema_principal"] == "p"
