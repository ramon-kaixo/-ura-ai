"""Tests para core/memoria/qdrant_store.py."""
from __future__ import annotations

from unittest import mock

import pytest

from core.memoria.ficha import Idea
from core.memoria.qdrant_store import (
    MemoryPipelineStore,
    _embed,
    _get_client,
    _make_id,
    almacenar_ideas,
    buscar_ideas,
    marcar_antiguas,
)


class FakeResp:
    def __init__(self, json_data=None, is_error=False):
        self._json = json_data if json_data is not None else {}
        self.is_error = is_error

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


@pytest.fixture(autouse=True)
def _reset_client(monkeypatch):
    monkeypatch.setattr("core.memoria.qdrant_store._client", None)
    yield
    monkeypatch.setattr("core.memoria.qdrant_store._client", None)


def _idea(hash_origen="h1", idea_text="idea uno") -> Idea:
    return Idea(
        idea=idea_text,
        tema="tema",
        etiquetas=["a"],
        tipo="herramienta",
        herramienta="Canva",
        coste="gratis",
        fuente="f",
        hash_origen=hash_origen,
        version=1,
        vigente=True,
    )


class TestGetClient:
    def test_singleton(self, monkeypatch) -> None:
        mock_client = mock.Mock()
        monkeypatch.setattr("core.memoria.qdrant_store.QdrantClient", mock.Mock(return_value=mock_client))
        a = _get_client()
        b = _get_client()
        assert a is b is mock_client

    def test_init_con_host(self, monkeypatch) -> None:
        qdrant_cls = mock.Mock()
        monkeypatch.setattr("core.memoria.qdrant_store.QdrantClient", qdrant_cls)
        _get_client()
        qdrant_cls.assert_called_once_with("127.0.0.1", port=6333)


class TestEmbed:
    @pytest.mark.asyncio
    async def test_ok(self, monkeypatch) -> None:
        class Cliente:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, **kw):
                return FakeResp(json_data={"embedding": [0.1, 0.2]})

        monkeypatch.setattr("core.memoria.qdrant_store.httpx.AsyncClient", lambda *a, **k: Cliente())
        assert await _embed("texto") == [0.1, 0.2]


class TestMakeId:
    def test_con_hash_origen(self) -> None:
        idea = _idea(hash_origen="abc")
        ident = _make_id(idea)
        assert ident == _make_id(idea)
        assert isinstance(ident, str)

    def test_sin_hash_usa_idea(self) -> None:
        idea = _idea(hash_origen="")
        ident = _make_id(idea)
        assert isinstance(ident, str)


class TestAlmacenarIdeas:
    @pytest.mark.asyncio
    async def test_lista_vacia(self) -> None:
        assert await almacenar_ideas([]) == 0

    @pytest.mark.asyncio
    async def test_inserta_nuevas(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        # Primera llamada: busqueda existente -> vacio; segunda: upsert OK
        http_client.post.return_value = FakeResp(json_data={"result": []})
        http_client.put.return_value = FakeResp(json_data={})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.1]))

        ideas = [_idea("h1"), _idea("h2")]
        n = await almacenar_ideas(ideas)
        assert n == 2
        assert http_client.put.call_count == 2

    @pytest.mark.asyncio
    async def test_existente_se_omite(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.post.return_value = FakeResp(json_data={"result": [{"id": "x"}]})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.1]))

        n = await almacenar_ideas([_idea("h1")])
        assert n == 0
        http_client.put.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_existing_check_continua(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.post.side_effect = RuntimeError("net")
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.1]))

        n = await almacenar_ideas([_idea("h1")])
        assert n == 1

    @pytest.mark.asyncio
    async def test_error_embedding_omite_idea(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.post.return_value = FakeResp(json_data={"result": []})
        http_client.put.return_value = FakeResp(json_data={})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(side_effect=RuntimeError("emb")))

        n = await almacenar_ideas([_idea("h1"), _idea("h2")])
        assert n == 0

    @pytest.mark.asyncio
    async def test_error_upsert_no_rompe(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.post.return_value = FakeResp(json_data={"result": []})
        http_client.put.side_effect = RuntimeError("upsert fail")
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.1]))

        n = await almacenar_ideas([_idea("h1")])
        assert n == 0


class TestMarcarAntiguas:
    @pytest.mark.asyncio
    async def test_una_pagina(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        puntos = [
            {"id": "1", "payload": {"vigente": True, "idea": "a"}},
            {"id": "2", "payload": {"vigente": True, "idea": "b"}},
        ]
        http_client.post.return_value = FakeResp(json_data={"result": {"points": puntos}})
        http_client.put.return_value = FakeResp(json_data={})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)

        n = await marcar_antiguas("https://fuente.com")
        assert n == 2
        # 1 scroll + 1 set por cada punto = 3 posts + 2 puts... post x2 (scroll), put x2
        assert http_client.put.call_count == 2
        # payload marcado vigente=False
        arg = http_client.put.call_args_list[0].kwargs["json"]["points"][0]["payload"]
        assert arg["vigente"] is False

    @pytest.mark.asyncio
    async def test_scroll_error_rompe(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.post.side_effect = RuntimeError("scroll fail")
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)

        n = await marcar_antiguas("https://fuente.com")
        assert n == 0

    @pytest.mark.asyncio
    async def test_paginacion_multiples_offsets(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        pagina1 = [{"id": f"p{i}", "payload": {"vigente": True}} for i in range(50)]
        pagina2 = [{"id": "extra", "payload": {"vigente": True}}]
        http_client.post.side_effect = [
            FakeResp(json_data={"result": {"points": pagina1}}),
            FakeResp(json_data={"result": {"points": pagina2}}),
        ]
        http_client.put.return_value = FakeResp(json_data={})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        monkeypatch.setattr("core.memoria.qdrant_store.URAQdrantClient", lambda: qdrant_async)

        n = await marcar_antiguas("https://fuente.com")
        assert n == 51
        assert http_client.post.call_count == 2


class TestBuscarIdeas:
    @pytest.mark.asyncio
    async def test_busqueda_basica(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.5]))
        puntos = [
            {"score": 0.9, "id": "a", "payload": {"idea": "x", "tema": "t"}},
            {"score": 0.5, "id": "b", "payload": {"idea": "y"}},
        ]

        class Cliente:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, **kw):
                self.json_body = json
                return FakeResp(json_data={"result": puntos})

        cliente = Cliente()
        monkeypatch.setattr("core.memoria.qdrant_store.httpx.AsyncClient", lambda *a, **k: cliente)

        out = await buscar_ideas("mi query")
        assert len(out) == 2
        assert out[0]["score"] == 0.9
        assert out[0]["idea"] == "x"
        assert cliente.json_body["vector"]["name"] == "texto"
        assert cliente.json_body["vector"]["vector"] == [0.5]
        assert cliente.json_body["filter"]["must"][0] == {"key": "vigente", "match": {"value": True}}
        assert cliente.json_body["limit"] == 5

    @pytest.mark.asyncio
    async def test_filtros_opcionales(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.qdrant_store._embed", mock.AsyncMock(return_value=[0.5]))

        class Cliente:
            def __init__(self, *a, **k):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *a):
                return False

            async def post(self, url, json=None, **kw):
                self.json_body = json
                return FakeResp(json_data={"result": []})

        cliente = Cliente()
        monkeypatch.setattr("core.memoria.qdrant_store.httpx.AsyncClient", lambda *a, **k: cliente)

        await buscar_ideas("q", tema="t", tipo="herramienta", coste="gratis", limit=3)
        must = cliente.json_body["filter"]["must"]
        assert len(must) == 4
        assert {"key": "tema", "match": {"value": "t"}} in must
        assert {"key": "tipo", "match": {"value": "herramienta"}} in must
        assert {"key": "coste", "match": {"value": "gratis"}} in must
        assert cliente.json_body["limit"] == 3


class TestMemoryPipelineStore:
    @pytest.mark.asyncio
    async def test_guardar_ok(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.put.return_value = FakeResp(json_data={})
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        store = MemoryPipelineStore(qdrant_client=qdrant_async)

        ok = await store.guardar_contexto_ingestado("ctx", [{"id": "1", "vector": [0.1]}])
        assert ok is True
        http_client.put.assert_awaited_once()
        assert http_client.put.await_args.kwargs["params"] == {"wait": "true"}

    @pytest.mark.asyncio
    async def test_guardar_sin_puntos(self) -> None:
        store = MemoryPipelineStore(qdrant_client=mock.Mock())
        assert await store.guardar_contexto_ingestado("ctx", []) is False

    @pytest.mark.asyncio
    async def test_guardar_error(self, monkeypatch) -> None:
        http_client = mock.AsyncMock()
        http_client.put.side_effect = RuntimeError("boom")
        qdrant_async = mock.Mock()
        qdrant_async._get_client = mock.AsyncMock(return_value=http_client)
        store = MemoryPipelineStore(qdrant_client=qdrant_async)

        ok = await store.guardar_contexto_ingestado("ctx", [{"id": "1"}])
        assert ok is False
