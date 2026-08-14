"""Tests para core/memoria/compresor.py — comprimir_a_ideas.

Cubre: texto vacío, éxito, error HTTP, JSON inválido, JSON embebido,
lista no-dict, items sin "idea", parseo de etiquetas/tipo/herramienta.
"""
from __future__ import annotations

import json

import pytest

from core.memoria.compresor import (
    MAX_CHARS_TEXTO,
    PROMPT_COMPRESOR,
    comprimir_a_ideas,
)


@pytest.mark.asyncio
async def test_texto_vacio_retorna_lista_vacia() -> None:
    assert await comprimir_a_ideas("") == []


@pytest.mark.asyncio
async def test_texto_solo_espacios() -> None:
    assert await comprimir_a_ideas("   \n  ") == []


@pytest.mark.asyncio
async def test_error_http_retorna_vacio(monkeypatch) -> None:
    class RespError:
        is_error = True
        status_code = 500

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespError()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    assert await comprimir_a_ideas("hola") == []


@pytest.mark.asyncio
async def test_respuesta_ok_parsea_ideas(monkeypatch) -> None:
    items = [
        {"idea": "Usa Canva para menus", "tema": "diseno", "etiquetas": ["gratis"], "tipo": "herramienta", "herramienta": "Canva", "coste": "gratis"},
        {"idea": "Automatiza con n8n", "tema": "ia"},
    ]
    content = json.dumps(items)

    class RespOk:
        is_error = False
        status_code = 200

        def json(self):
            return {"message": {"content": content}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            self.passthrough = True

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    ideas = await comprimir_a_ideas("texto", fuente="fu", hash_origen="h", fecha_fuente="2026-01-01")
    assert len(ideas) == 2
    assert ideas[0].idea == "Usa Canva para menus"
    assert ideas[0].tema == "diseno"
    assert ideas[0].etiquetas == ["gratis"]
    assert ideas[0].tipo == "herramienta"
    assert ideas[0].herramienta == "Canva"
    assert ideas[0].coste == "gratis"
    assert ideas[0].fuente == "fu"
    assert ideas[0].hash_origen == "h:0"
    assert ideas[0].fecha_fuente == "2026-01-01"
    assert ideas[1].hash_origen == "h:1"
    assert ideas[1].tipo == "dato"


@pytest.mark.asyncio
async def test_json_invalido_pero_embebido(monkeypatch) -> None:
    content = 'texto antes [{"idea": "solo idea"}] texto despues'

    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": content}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    ideas = await comprimir_a_ideas("texto")
    assert len(ideas) == 1
    assert ideas[0].idea == "solo idea"


@pytest.mark.asyncio
async def test_json_completamente_invalido(monkeypatch) -> None:
    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": "esto no es json"}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    assert await comprimir_a_ideas("texto") == []


@pytest.mark.asyncio
async def test_respuesta_no_lista(monkeypatch) -> None:
    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": '{"clave": "valor"}'}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    assert await comprimir_a_ideas("texto") == []


@pytest.mark.asyncio
async def test_items_invalidos_se_ignoran(monkeypatch) -> None:
    content = json.dumps([{"sin_idea": True}, {"idea": "   "}, 42, "string"])

    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": content}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    ideas = await comprimir_a_ideas("texto")
    assert ideas == []


@pytest.mark.asyncio
async def test_etiquetas_no_lista_se_normaliza(monkeypatch) -> None:
    content = json.dumps([{"idea": "x", "etiquetas": "no-lista"}])

    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": content}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **kw):
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    ideas = await comprimir_a_ideas("texto")
    assert ideas[0].etiquetas == []


@pytest.mark.asyncio
async def test_prompt_usa_modelo_y_truca_texto(monkeypatch) -> None:
    capturado: dict = {}

    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": "[]"}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            capturado["url"] = url
            capturado["json"] = json
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    texto_largo = "a" * (MAX_CHARS_TEXTO + 100)
    await comprimir_a_ideas(texto_largo, modelo="mi-modelo")
    assert capturado["url"] == "http://127.0.0.1:11434/api/chat"
    assert capturado["json"]["model"] == "mi-modelo"
    assert capturado["json"]["stream"] is False
    assert len(capturado["json"]["messages"][0]["content"]) == len(PROMPT_COMPRESOR.format(texto="a" * MAX_CHARS_TEXTO))


@pytest.mark.asyncio
async def test_modelo_default_qwen(monkeypatch) -> None:
    capturado: dict = {}

    class RespOk:
        is_error = False

        def json(self):
            return {"message": {"content": "[]"}}

    class ClienteFake:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, url, json=None, **kw):
            capturado["json"] = json
            return RespOk()

    monkeypatch.setattr("core.memoria.compresor.httpx.AsyncClient", ClienteFake)
    await comprimir_a_ideas("hola")
    assert capturado["json"]["model"] == "qwen2.5-coder:14b"


class TestCoberturaCompresorRemanente:
    """Cobertura 100x100: remanentes compresor (TASK-20260814-001)."""

    def test_json_interno_invalido(self) -> None:
        from core.memoria.compresor import _parsear_json_ideas

        assert _parsear_json_ideas("texto [no-es-json] resto") is None

    def test_sin_nada(self) -> None:
        from core.memoria.compresor import _parsear_json_ideas

        assert _parsear_json_ideas("sin corchetes") is None
        assert _parsear_json_ideas('{"clave": 1}') is None
