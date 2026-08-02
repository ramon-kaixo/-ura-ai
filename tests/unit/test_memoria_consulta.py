"""Tests para core/memoria/consulta.py — consultar, CPUReRanker, PipelineConsultaRAG."""
from __future__ import annotations

from unittest import mock

import pytest

from core.memoria.consulta import (
    CPUReRanker,
    PipelineConsultaRAG,
    _es_suficiente,
    consultar,
)


class TestEsSuficiente:
    def test_vacio_no_suficiente(self) -> None:
        assert _es_suficiente([]) is False

    def test_menos_de_3_buenas(self) -> None:
        rs = [
            {"score": 0.8},
            {"score": 0.7},
            {"score": 0.2},
        ]
        assert _es_suficiente(rs) is False

    def test_3_o_mas_buenas(self) -> None:
        rs = [{"score": 0.8}, {"score": 0.7}, {"score": 0.6}]
        assert _es_suficiente(rs) is True

    def test_mezcla(self) -> None:
        rs = [{"score": 0.9}, {"score": 0.4}, {"score": 0.6}, {"score": 0.55}]
        assert _es_suficiente(rs) is True


class TestConsultar:
    @pytest.mark.asyncio
    async def test_suficiente_memoria_sin_web(self, monkeypatch) -> None:
        ideas = [{"score": 0.8}, {"score": 0.7}, {"score": 0.6}]
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=ideas))
        llamadas = []
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(side_effect=lambda *a, **k: llamadas.append(1) or []))
        out = await consultar("pregunta")
        assert out["desde"] == "memoria"
        assert out["busqueda_web"] is False
        assert out["total_ideas"] == 3
        assert llamadas == []

    @pytest.mark.asyncio
    async def test_suficiente_pero_forzar_web(self, monkeypatch) -> None:
        ideas = [{"score": 0.8}, {"score": 0.7}, {"score": 0.6}]
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=ideas))
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=[]))
        out = await consultar("pregunta", forzar_web=True)
        assert out["busqueda_web"] is True
        assert out["desde"] == "memoria+web"

    @pytest.mark.asyncio
    async def test_sin_memoria_web_sin_ideas(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=[]))
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=[]))
        out = await consultar("pregunta")
        assert out["desde"] == "web"
        assert out["ideas"] == []
        assert out["ideas_nuevas_web"] == 0
        assert out["paginas_procesadas"] == 0

    @pytest.mark.asyncio
    async def test_web_procesada_comprime_y_almacena(self, monkeypatch) -> None:
        ideas_memoria_inicial = [{"score": 0.3}]
        ideas_actualizadas = [{"score": 0.9}, {"score": 0.8}, {"score": 0.7}, {"score": 0.6}]
        buscar_ideas = mock.AsyncMock(side_effect=[ideas_memoria_inicial, ideas_actualizadas])
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", buscar_ideas)

        web_results = [
            {
                "procesado": {
                    "extraido": {"texto_plano": "texto util"},
                    "hash": "abc123",
                },
                "fuente": "https://ejemplo.com",
            }
        ]
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=web_results))

        ideas_comprimidas = [mock.Mock()]
        comprimir = mock.AsyncMock(return_value=ideas_comprimidas)
        almacenar = mock.AsyncMock(return_value=2)
        monkeypatch.setattr("core.memoria.compresor.comprimir_a_ideas", comprimir)
        monkeypatch.setattr("core.memoria.qdrant_store.almacenar_ideas", almacenar)

        out = await consultar("pregunta")
        assert out["desde"] == "memoria+web"
        assert out["ideas_nuevas_web"] == 2
        assert out["paginas_procesadas"] == 1
        comprimir.assert_awaited_once()
        kwargs = comprimir.await_args.kwargs
        assert kwargs["fuente"] == "https://ejemplo.com"
        assert kwargs["hash_origen"] == "abc123"
        assert buscar_ideas.await_count == 2

    @pytest.mark.asyncio
    async def test_web_sin_extraido(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=[]))
        web_results = [{"procesado": {"hash": "x", "extraido": {}}}]
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=web_results))
        out = await consultar("pregunta")
        assert out["ideas_nuevas_web"] == 0
        assert out["paginas_procesadas"] == 1

    @pytest.mark.asyncio
    async def test_web_sin_texto_plano(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=[]))
        web_results = [{"procesado": {"hash": "x", "extraido": {"texto_plano": ""}}}]
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=web_results))
        out = await consultar("pregunta")
        assert out["ideas_nuevas_web"] == 0

    @pytest.mark.asyncio
    async def test_web_sin_procesado(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=[]))
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=[{"url": "x"}]))
        out = await consultar("pregunta")
        assert out["paginas_procesadas"] == 0
        assert out["ideas_nuevas_web"] == 0

    @pytest.mark.asyncio
    async def test_excepcion_al_comprimir_no_rompe(self, monkeypatch) -> None:
        monkeypatch.setattr("core.memoria.consulta.buscar_ideas", mock.AsyncMock(return_value=[]))
        web_results = [
            {
                "procesado": {
                    "extraido": {"texto_plano": "texto"},
                    "hash": "abc",
                },
                "fuente": "f",
            }
        ]
        monkeypatch.setattr("core.memoria.consulta.buscar_y_aprender", mock.AsyncMock(return_value=web_results))
        monkeypatch.setattr("core.memoria.compresor.comprimir_a_ideas", mock.AsyncMock(side_effect=RuntimeError("boom")))
        monkeypatch.setattr("core.memoria.qdrant_store.almacenar_ideas", mock.AsyncMock())
        out = await consultar("pregunta")
        assert out["ideas_nuevas_web"] == 0


class TestCPUReRanker:
    def test_inicializa(self) -> None:
        r = CPUReRanker()
        assert r.modelo_cargado is True

    def test_score_coincidencia_total(self) -> None:
        r = CPUReRanker()
        assert r._calcular_score_cross_encoder("hola mundo", "hola mundo") == pytest.approx(1.0)

    def test_score_parcial(self) -> None:
        r = CPUReRanker()
        s = r._calcular_score_cross_encoder("hola mundo", "hola sol")
        assert 0.1 < s < 1.0

    def test_score_sin_coincidencias(self) -> None:
        r = CPUReRanker()
        assert r._calcular_score_cross_encoder("a b", "x y z") == pytest.approx(0.1)

    @pytest.mark.asyncio
    async def test_reordenar_vacio(self) -> None:
        r = CPUReRanker()
        assert await r.reordenar_resultados("q", []) == []

    @pytest.mark.asyncio
    async def test_reordenar_ordena_y_recorta(self) -> None:
        r = CPUReRanker()
        docs = [
            {"payload": {"texto": "uno dos tres"}, "id": 1},
            {"payload": {"texto": "uno"}, "id": 2},
            {"payload": {"texto": "uno dos"}, "id": 3},
            {"payload": {"texto": "cero"}, "id": 4},
        ]
        out = await r.reordenar_resultados("uno dos tres", docs, top_n=2)
        assert [d["id"] for d in out] == [1, 3]
        assert out[0]["score_rerank"] > out[1]["score_rerank"]

    @pytest.mark.asyncio
    async def test_reordenar_sin_payload(self) -> None:
        r = CPUReRanker()
        docs = [{"id": 1}, {"payload": {"texto": "q"}, "id": 2}]
        out = await r.reordenar_resultados("q", docs, top_n=5)
        assert len(out) == 2


class TestPipelineConsultaRAG:
    @pytest.mark.asyncio
    async def test_recuperar_contexto(self) -> None:
        qdrant = mock.AsyncMock()
        qdrant.buscar_hibrido.return_value = [
            {"payload": {"texto": "uno dos tres"}, "id": 1},
            {"payload": {"texto": "uno"}, "id": 2},
            {"payload": {"texto": "otro"}, "id": 3},
        ]
        reranker = CPUReRanker()
        pipe = PipelineConsultaRAG(qdrant, reranker=reranker)
        out = await pipe.recuperar_contexto_optimo("uno dos tres", "coleccion", [0.1, 0.2])
        assert len(out) == 3
        qdrant.buscar_hibrido.assert_awaited_once_with("coleccion", "uno dos tres", [0.1, 0.2], limite=10)
        assert out[0]["id"] == 1

    @pytest.mark.asyncio
    async def test_recuperar_reranker_default(self) -> None:
        qdrant = mock.AsyncMock()
        qdrant.buscar_hibrido.return_value = []
        pipe = PipelineConsultaRAG(qdrant)
        out = await pipe.recuperar_contexto_optimo("q", "c", [])
        assert out == []
