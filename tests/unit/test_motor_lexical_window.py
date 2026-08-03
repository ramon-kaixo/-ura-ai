"""Tests para motor/intelligence/retrieval/lexical.py, motor/assistant/context_window.py y motor/core/llm/_logging.py."""
from __future__ import annotations

from unittest import mock

from motor.assistant.context_window import ContextWindow
from motor.core.llm._logging import log_call, percentile
from motor.intelligence.retrieval.lexical import LexicalRetriever


class TestLexicalRetriever:
    def test_docs_dir_no_existe(self) -> None:
        r = LexicalRetriever("/tmp/no_existe_docs_xyz")
        assert r._docs == []
        assert r._bm25 is None
        assert r.search("query") == []

    def test_carga_docs(self, tmp_path) -> None:
        (tmp_path / "doc1.md").write_text("El gato caza ratones en el jardín.")
        (tmp_path / "doc2.md").write_text("Los perros ladran a los gatos.")
        r = LexicalRetriever(tmp_path)
        assert len(r._docs) == 2
        assert r._bm25 is not None
        assert r._docs[0]["source"] == "doc1"

    def _corpus(self, tmp_path) -> None:
        docs = {
            "gatos": "el gato gato gato gato caza ratones en el jardin",
            "perros": "el perro perro perro pasea por el parque",
            "coches": "el coche coche coche corre por la carretera",
            "barcos": "el barco barco barco navega por el mar",
        }
        for name, text in docs.items():
            (tmp_path / f"{name}.md").write_text(text)

    def test_search_ok(self, tmp_path) -> None:
        self._corpus(tmp_path)
        r = LexicalRetriever(tmp_path)
        results = r.search("gato gato gato gato", k=5)
        assert len(results) == 1
        assert results[0]["doc_id"] == "gatos"
        assert results[0]["source"] == "lexical"
        assert results[0]["score"] > 0

    def test_search_ranking(self, tmp_path) -> None:
        self._corpus(tmp_path)
        (tmp_path / "gatos2.md").write_text("gato gato gato gato gato gato gato gato")
        r = LexicalRetriever(tmp_path)
        results = r.search("gato gato gato gato", k=5)
        assert results[0]["doc_id"] == "gatos2"  # mas relevante primero

    def test_search_sin_match(self, tmp_path) -> None:
        self._corpus(tmp_path)
        r = LexicalRetriever(tmp_path)
        assert r.search("zzzqqq wwww", k=5) == []

    def test_sin_bm25_retorna_vacio(self) -> None:
        r = LexicalRetriever("/tmp/no_existe")
        assert r.search("q") == []


class TestContextWindow:
    def _msg(self, content: str):
        m = mock.Mock()
        m.token_estimate.return_value = len(content) // 4 + 1
        return m

    def test_build_context_limita(self) -> None:
        cw = ContextWindow(max_tokens=100, reserve_tokens=20)
        msgs = [self._msg("a" * 80), self._msg("b" * 80), self._msg("c" * 80)]
        selected = cw.build_context(msgs)
        # budget 80, cada msg cuesta 21 -> caben 3
        assert len(selected) == 3

    def test_build_context_con_system(self) -> None:
        cw = ContextWindow(max_tokens=100, reserve_tokens=20)
        msgs = [self._msg("a" * 30)]
        # system de 100 chars cuesta 26 -> disponible 54 -> cabe 1 msg (8)
        selected = cw.build_context(msgs, system_prompt="x" * 100)
        assert len(selected) == 1

    def test_build_context_system_consume_todo(self) -> None:
        cw = ContextWindow(max_tokens=100, reserve_tokens=20)
        msgs = [self._msg("a" * 30)]
        # system de 500 chars cuesta 126 > budget 80 -> nada cabe
        selected = cw.build_context(msgs, system_prompt="x" * 500)
        assert selected == []

    def test_build_context_todo_cabe(self) -> None:
        cw = ContextWindow(max_tokens=1000, reserve_tokens=20)
        msgs = [self._msg("a" * 10), self._msg("b" * 10)]
        assert len(cw.build_context(msgs)) == 2

    def test_build_context_vacio(self) -> None:
        cw = ContextWindow()
        assert cw.build_context([]) == []

    def test_trim_to_budget(self) -> None:
        cw = ContextWindow()
        msgs = [self._msg("a" * 50), self._msg("b" * 50), self._msg("c" * 50)]
        selected = cw.trim_to_budget(msgs, max_tokens=40)
        # cada msg cuesta 13 -> caben 3 en 40
        assert len(selected) == 3

    def test_trim_default_budget(self) -> None:
        cw = ContextWindow(max_tokens=100, reserve_tokens=20)
        msgs = [self._msg("a" * 80)]
        assert len(cw.trim_to_budget(msgs)) == 1


class TestLoggingUtils:
    def test_percentile(self) -> None:
        assert percentile([], 50) == 0.0
        assert percentile([1, 2, 3, 4, 5], 50) == 3
        assert percentile([1, 2, 3, 4, 5], 0) == 1
        assert percentile([1, 2, 3, 4, 5], 100) == 5

    def test_log_call_info(self, monkeypatch) -> None:
        logger = mock.Mock()
        monkeypatch.setattr("motor.core.llm._logging.log", logger)
        log_call("ollama", "qwen", 10.0, extra={"tokens": 100})
        logger.info.assert_called_once()
        assert "ollama" in logger.info.call_args.args

    def test_log_call_error(self, monkeypatch) -> None:
        logger = mock.Mock()
        monkeypatch.setattr("motor.core.llm._logging.log", logger)
        log_call("ollama", "qwen", 10.0, error="timeout", intent="chat")
        logger.warning.assert_called_once()
        assert "timeout" in logger.warning.call_args.args

    def test_log_call_sin_extra(self, monkeypatch) -> None:
        logger = mock.Mock()
        monkeypatch.setattr("motor.core.llm._logging.log", logger)
        log_call("p", "m", 5.0)
        logger.info.assert_called_once()
