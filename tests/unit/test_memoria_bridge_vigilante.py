"""Tests para core/memoria/bridge.py, vigilante.py y ingesto.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

from core.memoria.bridge import _guardar_en_inbox, buscar_y_aprender
from core.memoria.ingesto import procesar_archivo, procesar_inbox_completo
from core.memoria.vigilante import (
    cargar_fuentes,
    fuente_a_texto,
    generar_parte,
    guardar_fuentes,
    procesar_cambios,
    revisar_fuente,
)


def _patch_blake3(monkeypatch, hexdigest: str) -> mock.Mock:
    """Simula el modulo blake3 (import lazy dentro de revisar_fuente)."""
    hasher = mock.Mock()
    hasher.update.return_value = None
    hasher.hexdigest.return_value = hexdigest
    fake_module = mock.Mock(blake3=lambda: hasher)
    monkeypatch.setitem(sys.modules, "blake3", fake_module)
    return hasher


class TestGuardarEnInbox:
    def test_guardar_crea_html(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        ruta = _guardar_en_inbox("https://ejemplo.com/articulo?a=1", "Titulo", "contenido")
        assert ruta is not None
        assert ruta.parent == tmp_path
        assert ruta.name.endswith(".html")
        html = ruta.read_text(encoding="utf-8")
        assert "<title>Titulo</title>" in html
        assert "<pre>contenido</pre>" in html

    def test_guardar_error_oserror(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        with mock.patch.object(Path, "write_text", side_effect=OSError("ro")):
            assert _guardar_en_inbox("https://x.com", "t", "c") is None

    def test_slug_url_vacia(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        ruta = _guardar_en_inbox("", "", "c")
        assert ruta is not None


class TestBuscarYAprender:
    @pytest.mark.asyncio
    async def test_error_busqueda(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "core.memoria.bridge.web_search", mock.AsyncMock(return_value={"error": "API caida"})
        )
        assert await buscar_y_aprender("q") == []

    @pytest.mark.asyncio
    async def test_flujo_completo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        search = {
            "results": [
                {"url": "https://a.com/1", "title": "T1", "snippet": "s1"},
                {"url": "https://b.com/2", "title": "T2", "snippet": "s2"},
            ]
        }
        monkeypatch.setattr("core.memoria.bridge.web_search", mock.AsyncMock(return_value=search))
        monkeypatch.setattr("core.memoria.bridge.page_read", mock.AsyncMock(return_value={"content": "texto pagina"}))

        procesado = {"hash": "h1", "tipo": "web", "extraido": {"metadatos": {"m": 1}, "texto_plano": "abc"}}
        monkeypatch.setattr("core.memoria.bridge.procesar_archivo", mock.Mock(return_value=procesado))
        monkeypatch.setattr("core.memoria.bridge.asyncio.sleep", mock.AsyncMock())

        out = await buscar_y_aprender("q", max_resultados=2)
        assert len(out) == 2
        assert out[0]["fuente"] == "https://a.com/1"
        assert out[0]["titulo"] == "T1"
        assert out[0]["snippet"] == "s1"
        assert out[0]["procesado"]["hash"] == "h1"
        assert out[0]["procesado"]["texto_longitud"] == 3

    @pytest.mark.asyncio
    async def test_item_sin_url_se_omite(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        search = {"results": [{"title": "sin url"}]}
        monkeypatch.setattr("core.memoria.bridge.web_search", mock.AsyncMock(return_value=search))
        out = await buscar_y_aprender("q")
        assert out == []

    @pytest.mark.asyncio
    async def test_page_read_error_continua(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        search = {"results": [{"url": "https://a.com", "title": "T"}]}
        monkeypatch.setattr("core.memoria.bridge.web_search", mock.AsyncMock(return_value=search))
        monkeypatch.setattr("core.memoria.bridge.page_read", mock.AsyncMock(return_value={"error": "404"}))
        out = await buscar_y_aprender("q")
        assert out == []

    @pytest.mark.asyncio
    async def test_page_read_excepcion_continua(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        search = {"results": [{"url": "https://a.com", "title": "T"}]}
        monkeypatch.setattr("core.memoria.bridge.web_search", mock.AsyncMock(return_value=search))
        monkeypatch.setattr("core.memoria.bridge.page_read", mock.AsyncMock(side_effect=RuntimeError("net")))
        out = await buscar_y_aprender("q")
        assert out == []

    @pytest.mark.asyncio
    async def test_procesar_archivo_none(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.bridge.INBOX", tmp_path)
        search = {"results": [{"url": "https://a.com", "title": "T"}]}
        monkeypatch.setattr("core.memoria.bridge.web_search", mock.AsyncMock(return_value=search))
        monkeypatch.setattr("core.memoria.bridge.page_read", mock.AsyncMock(return_value={"content": "x"}))
        monkeypatch.setattr("core.memoria.bridge.procesar_archivo", mock.Mock(return_value=None))
        out = await buscar_y_aprender("q")
        assert len(out) == 1
        assert out[0]["procesado"] is None


class TestVigilanteFuentes:
    def test_cargar_sin_archivo(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", tmp_path / "nope.json")
        assert cargar_fuentes() == []

    def test_cargar_y_guardar_roundtrip(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "fuentes.json"
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", f)
        guardar_fuentes([{"url": "u", "tema": "t"}])
        assert cargar_fuentes() == [{"url": "u", "tema": "t"}]

    def test_guardar_corrupto(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "fuentes.json"
        f.write_text("not json")
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", f)
        with pytest.raises(json.JSONDecodeError):
            cargar_fuentes()

    def test_fuente_a_texto(self) -> None:
        assert fuente_a_texto({"content": "abc"}) == "abc"
        assert fuente_a_texto({}) == ""
        assert fuente_a_texto({"otro": 1}) == ""


class TestVigilanteRevisar:
    @pytest.mark.asyncio
    async def test_sin_cambio(self, monkeypatch) -> None:
        _patch_blake3(monkeypatch, "hash1")
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(return_value={"content": "texto"}))
        fuente = {"url": "u", "hash_actual": "hash1"}
        out = await revisar_fuente(fuente)
        assert out["cambio"] is False

    @pytest.mark.asyncio
    async def test_con_cambio(self, monkeypatch) -> None:
        _patch_blake3(monkeypatch, "hash2")
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(return_value={"content": "nuevo texto"}))
        fuente = {"url": "u", "tema": "t", "hash_actual": "hash1"}
        out = await revisar_fuente(fuente)
        assert out["cambio"] is True
        assert out["hash"] == "hash2"
        assert out["texto"] == "nuevo texto"
        assert out["metadatos"]["tema"] == "t"
        assert fuente["hash_actual"] == "hash2"
        assert "ultima_revision" in fuente

    @pytest.mark.asyncio
    async def test_primer_revision_sin_hash_anterior_es_cambio(self, monkeypatch) -> None:
        _patch_blake3(monkeypatch, "h3")
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(return_value={"content": "x"}))
        out = await revisar_fuente({"url": "u"})
        assert out["cambio"] is True

    @pytest.mark.asyncio
    async def test_error_lectura(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(side_effect=OSError("net")))
        out = await revisar_fuente({"url": "u"})
        assert "error" in out
        assert out["cambio"] is False

    @pytest.mark.asyncio
    async def test_pagina_con_error(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(return_value={"error": "404"}))
        out = await revisar_fuente({"url": "u"})
        assert out["error"] == "404"

    @pytest.mark.asyncio
    async def test_pagina_sin_contenido(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.vigilante.page_read", mock.AsyncMock(return_value={}))
        out = await revisar_fuente({"url": "u"})
        assert out["cambio"] is False


class TestVigilanteProcesar:
    @pytest.mark.asyncio
    async def test_sin_fuentes(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=[]))
        assert await procesar_cambios() == []

    @pytest.mark.asyncio
    async def test_sin_cambios_guarda(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "fuentes.json"
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", f)
        monkeypatch.setattr(
            "core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=[{"url": "u", "hash_actual": "h"}])
        )
        monkeypatch.setattr("core.memoria.vigilante.revisar_fuente", mock.AsyncMock(return_value={"cambio": False}))
        assert await procesar_cambios() == []
        assert f.exists()

    @pytest.mark.asyncio
    async def test_con_cambios_comprime(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "fuentes.json"
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", f)
        monkeypatch.setattr(
            "core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=[{"url": "u", "hash_actual": "h"}])
        )
        cambio = {"cambio": True, "url": "u", "hash": "h2", "texto": "txt", "metadatos": {}}
        monkeypatch.setattr("core.memoria.vigilante.revisar_fuente", mock.AsyncMock(return_value=cambio))
        monkeypatch.setattr("core.memoria.compresor.comprimir_a_ideas", mock.AsyncMock(return_value=[mock.Mock(), mock.Mock()]))
        marcar = mock.AsyncMock()
        almacenar = mock.AsyncMock(return_value=2)
        monkeypatch.setattr("core.memoria.qdrant_store.marcar_antiguas", marcar)
        monkeypatch.setattr("core.memoria.qdrant_store.almacenar_ideas", almacenar)

        out = await procesar_cambios()
        assert len(out) == 1
        assert out[0]["ideas_insertadas"] == 2
        assert out[0]["total_ideas"] == 2
        marcar.assert_awaited_once_with("u")

    @pytest.mark.asyncio
    async def test_error_comprimiendo_no_rompe(self, monkeypatch, tmp_path) -> None:
        f = tmp_path / "fuentes.json"
        monkeypatch.setattr("core.memoria.vigilante.FUENTES_FILE", f)
        monkeypatch.setattr(
            "core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=[{"url": "u"}])
        )
        cambio = {"cambio": True, "url": "u", "hash": "h2", "texto": "txt", "metadatos": {}}
        monkeypatch.setattr("core.memoria.vigilante.revisar_fuente", mock.AsyncMock(return_value=cambio))
        monkeypatch.setattr("core.memoria.compresor.comprimir_a_ideas", mock.AsyncMock(side_effect=RuntimeError("boom")))
        out = await procesar_cambios()
        assert len(out) == 1
        assert "ideas_insertadas" not in out[0]


class TestVigilanteParte:
    @pytest.mark.asyncio
    async def test_sin_fuentes(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=[]))
        out = await generar_parte()
        assert out == {"pasada": 0, "fuentes_vigiladas": 0, "cambios": 0, "fallos": 0, "detalle": []}

    @pytest.mark.asyncio
    async def test_con_fuentes(self, monkeypatch) -> None:
        fuentes = [
            {"url": "https://a.com", "tema": "t", "intervalo_horas": 24, "ultima_revision": "2026-01-01"},
            {"url": "https://b.com", "tema": "t2"},
        ]
        monkeypatch.setattr("core.memoria.vigilante.cargar_fuentes", mock.Mock(return_value=fuentes))

        class P:
            def __init__(self, vigente, version):
                self.payload = {"vigente": vigente, "version": version}

        client = mock.Mock()
        client.query_points.return_value = mock.Mock(points=[P(True, 1), P(True, 2), P(False, 1)])
        monkeypatch.setattr("core.memoria.qdrant_store._get_client", mock.Mock(return_value=client))
        monkeypatch.setattr("core.memoria.vigilante.asyncio.to_thread", mock.AsyncMock(side_effect=[mock.Mock(points=[P(True, 1), P(False, 1)]), mock.Mock(points=[])]))

        out = await generar_parte()
        assert out["fuentes_vigiladas"] == 2
        assert out["pasada"] == 1
        assert out["cambios"] == 2
        assert out["fallos"] == 1
        assert len(out["detalle"]) == 2
        assert out["detalle"][1]["alerta"] == "sin_version_activa"


class TestIngesto:
    def test_procesar_archivo_stub(self) -> None:
        assert procesar_archivo(Path("/tmp/x.html")) is None

    @pytest.mark.asyncio
    async def test_procesar_inbox_stub(self) -> None:
        out = await procesar_inbox_completo()
        assert out == {"status": "stub", "procesados": 0, "errores": 0}
