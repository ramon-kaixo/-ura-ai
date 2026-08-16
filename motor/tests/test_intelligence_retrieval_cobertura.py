"""Cobertura 100x100: motor/intelligence/{chunking,pipeline,retrieval,reranking}."""

from __future__ import annotations

import sys
import types
from pathlib import Path
from typing import Any

import pytest


def _install_ce_deps() -> None:
    fake_torch = types.ModuleType("torch")
    fake_torch.cuda = types.SimpleNamespace(is_available=lambda: False)
    fake_torch.no_grad = lambda: _CtxMgr()
    fake_torch.manual_seed = lambda *a: None
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = types.SimpleNamespace()
    fake_transformers.AutoModelForSequenceClassification = types.SimpleNamespace()
    sys.modules.setdefault("torch", fake_torch)
    sys.modules.setdefault("transformers", fake_transformers)


class _CtxMgr:
    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: object) -> None:
        return None


_install_ce_deps()

from motor.intelligence.chunking import Chunk, SemanticChunker
from motor.intelligence.pipeline import (
    create_retrieval_pipeline,
    disable_reranker,
    enable_reranker,
    reranker_enabled,
    search_with_reranker,
)
from motor.intelligence.retrieval.hybrid import HybridRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever
from motor.intelligence.retrieval.vector import VectorRetriever

# ── chunking ────────────────────────────────────────────────────────────────


class TestSemanticChunker:
    def test_vacio(self) -> None:
        assert SemanticChunker().chunk("   ") == []
        assert SemanticChunker().chunk("") == []

    def test_chunk_index(self) -> None:
        assert Chunk(document_id="d", chunk_id="d_3").chunk_index == 3
        assert Chunk(document_id="d", chunk_id="d_x").chunk_index == 0
        assert Chunk(document_id="d", chunk_id="").chunk_index == 0

    def test_simple(self) -> None:
        c = SemanticChunker(max_tokens=1000)
        chunks = c.chunk("Hola mundo", doc_id="doc1", section="intro")
        assert len(chunks) == 1
        assert chunks[0].document_id == "doc1"
        assert chunks[0].chunk_id == "doc1_0"
        assert chunks[0].parent_id == "doc1"
        assert chunks[0].section == "intro"
        assert chunks[0].length == len("Hola mundo")
        assert chunks[0].offset == 0

    def test_sin_doc_id(self) -> None:
        chunks = SemanticChunker(max_tokens=1000).chunk("Texto")
        assert chunks[0].chunk_id == "chunk_0"

    def test_respect_headings_false(self) -> None:
        text = "## Titulo\n\nCuerpo"
        c = SemanticChunker(max_tokens=1000, respect_headings=False)
        chunks = c.chunk(text, doc_id="d")
        assert len(chunks) == 1
        assert "## Titulo" in chunks[0].texto

    def test_por_headings(self) -> None:
        text = "## Seccion A\n\nParrafo A1\n\n### Sub B\n\nParrafo B1\n\n## Seccion C\n\nParrafo C1"
        c = SemanticChunker(max_tokens=1000)
        chunks = c.chunk(text, doc_id="d")
        assert len(chunks) >= 3
        titles = {ch.section for ch in chunks}
        assert any("Seccion A" in t for t in titles)
        assert any("Seccion C" in t for t in titles)

    def test_sin_headings(self) -> None:
        c = SemanticChunker(max_tokens=1000)
        chunks = c.chunk("Solo texto", doc_id="d")
        assert len(chunks) == 1 and chunks[0].section == ""

    def test_preamble_sin_titulo(self) -> None:
        text = "Preamble text\n\n## Titulo\n\nCuerpo"
        c = SemanticChunker(max_tokens=1000)
        chunks = c.chunk(text, doc_id="d")
        assert chunks[0].section == ""

    def test_seccion_larga_por_parrafos(self) -> None:
        text = "\n\n".join(f"Parrafo numero {i} con contenido extenso" for i in range(30))
        c = SemanticChunker(max_tokens=50, overlap_tokens=20)
        chunks = c.chunk(text, doc_id="d", section="s")
        assert len(chunks) > 1
        assert all(ch.texto for ch in chunks)
        assert chunks[0].offset == 0
        assert chunks[1].offset > 0

    def test_parrafo_unico_largo(self) -> None:
        c = SemanticChunker(max_tokens=20)
        chunks = c.chunk("A" * 300, doc_id="d")
        assert len(chunks) == 1
        assert len(chunks[0].texto) <= 20 * 4

    def test_overlap_vacio(self) -> None:
        c = SemanticChunker()
        _paras, tokens = c._overlap_paragraphs(["a" * 500, "b" * 500])
        assert tokens == 0

    def test_estimacion_tokens(self) -> None:
        c = SemanticChunker()
        assert c._estimate_tokens("abcdefgh") == 2
        assert c._char_limit() == 512 * 4

    def test_split_sections_con_cuerpo_vacio(self) -> None:
        c = SemanticChunker()
        text = "## Titulo A\n\n\n\n## Titulo B\n\nContenido B"
        sections = c._split_by_headings(text)
        assert len(sections) >= 2
        assert any(t and "Titulo B" in t for t, _ in sections)

    def test_split_sections_sin_cuerpo_final(self) -> None:
        c = SemanticChunker()
        sections = c._split_by_headings("## Solo titulo")
        assert len(sections) == 1
        assert sections[0][0] == "Solo titulo"

    def test_split_sections_parrafos_mezclados(self) -> None:
        c = SemanticChunker()
        text = "Preamble\n\n## A\n\n1\n\n## B\n\n2\n\n## C\n\n3"
        sections = c._split_by_headings(text)
        assert len(sections) == 4
        titles = [t for t, _ in sections]
        assert "" in titles
        assert all(t in titles for t in ("A", "B", "C"))

    def test_chunk_section_sin_parrafos(self) -> None:
        c = SemanticChunker(max_tokens=10)
        chunks = c._chunk_section("   " * 100, "d", "s", 0)
        assert len(chunks) == 1
        assert chunks[0].section == "s"
        assert chunks[0].offset == 0

    def test_overlap_completo(self) -> None:
        c = SemanticChunker(overlap_tokens=100)
        paras, tokens = c._overlap_paragraphs(["aa", "bb", "cc"])
        assert paras == ["aa", "bb", "cc"]
        assert tokens == 0


# ── lexical ─────────────────────────────────────────────────────────────────


class TestLexicalRetriever:
    def test_dir_no_existe(self, tmp_path: Path) -> None:
        r = LexicalRetriever(tmp_path / "no_existe")
        assert r.search("algo") == []

    def test_dir_vacio(self, tmp_path: Path) -> None:
        r = LexicalRetriever(tmp_path)
        assert r._bm25 is None
        assert r.search("algo") == []

    def test_corpus_ok(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("python programming language", encoding="utf-8")
        (tmp_path / "b.md").write_text("java virtual machine", encoding="utf-8")
        (tmp_path / "c.md").write_text("forth stack based", encoding="utf-8")
        r = LexicalRetriever(tmp_path)
        res = r.search("python", k=2)
        assert len(res) == 1
        assert res[0]["doc_id"] == "a"
        assert res[0]["source"] == "lexical"
        assert res[0]["score"] > 0
        assert res[0]["latency_ms"] >= 0

    def test_scores_cero_filtrados(self, tmp_path: Path) -> None:
        (tmp_path / "a.md").write_text("hola mundo", encoding="utf-8")
        r = LexicalRetriever(tmp_path)
        res = r.search("palabrasque no coinciden", k=5)
        assert res == []


# ── vector ──────────────────────────────────────────────────────────────────


class _FakeQdrant:
    def __init__(self, client: Any = None) -> None:
        self._cliente = client

    def generar_embedding(self, query: str) -> list[float]:
        return [0.1, 0.2]


class _FakeHits:
    def __init__(self, points: list[Any]) -> None:
        self.points = points


class _FakePoint:
    def __init__(self, hid: Any, score: float, payload: Any) -> None:
        self.id = hid
        self.score = score
        self.payload = payload


class _FakeFeatures(dict):
    def to(self, device: Any) -> Any:
        return self


class _CtxMgr:
    def __enter__(self) -> Any:
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _FakeClient:
    def __init__(self, points: list[_FakePoint] | None = None) -> None:
        self._points = points or []

    def query_points(self, **kwargs: Any) -> _FakeHits:
        assert kwargs["collection_name"]
        assert kwargs["limit"] > 0
        assert kwargs["with_payload"] is True
        return _FakeHits(self._points)


class TestVectorRetriever:
    def test_qc_none(self) -> None:
        assert VectorRetriever(None).search("q") == []

    def test_sin_cliente(self) -> None:
        assert VectorRetriever(_FakeQdrant(None)).search("q") == []

    def test_hits_ok(self) -> None:
        qc = _FakeQdrant(
            _FakeClient(
                [
                    _FakePoint("p1", 0.9, {"source": "doc_x", "otro": 1}),
                    _FakePoint("p2", 0.5, None),
                ],
            ),
        )
        res = VectorRetriever(qc, collection="col").search("q", k=5)
        assert len(res) == 2
        assert res[0]["doc_id"] == "doc_x"
        assert res[0]["source"] == "vector"
        assert res[1]["doc_id"] == "p2"
        assert res[1]["score"] == 0.5
        assert res[1]["payload"] == {}
        assert res[0]["latency_ms"] >= 0

    def test_hits_vacio(self) -> None:
        qc = _FakeQdrant(_FakeClient([]))
        assert VectorRetriever(qc).search("q") == []


# ── hybrid ──────────────────────────────────────────────────────────────────


class _RetrieverStub:
    def __init__(self, results: list[dict[str, Any]] | None = None, fail: bool = False) -> None:
        self._results = results or []
        self._fail = fail

    def search(self, query: str, k: int = 10) -> list[dict[str, Any]]:
        if self._fail:
            raise RuntimeError("down")
        return self._results


class TestHybridRetriever:
    def test_fusion_completa(self) -> None:
        vec = _RetrieverStub(
            [
                {"doc_id": "a", "score": 0.9, "rank": 0},
                {"doc_id": "b", "score": 0.4, "rank": 1},
            ],
        )
        lex = _RetrieverStub(
            [
                {"doc_id": "b", "score": 0.8, "rank": 0},
                {"doc_id": "c", "score": 0.2, "rank": 1},
            ],
        )
        hr = HybridRetriever(vec, lex, alpha=0.7, beta=0.3)
        res = hr.search("q", k=2)
        assert len(res) == 2
        assert res[0]["source"] == "hybrid"
        by_id = {r["doc_id"]: r for r in res}
        assert "hybrid_score" in by_id["a"]
        assert by_id["b"]["vector_score"] == pytest.approx(0.4444, abs=0.01)
        assert by_id["b"]["lexical_score"] == 1.0
        assert by_id["a"]["vector_score"] == 1.0
        # valores exactos de rank y scores híbridos
        assert by_id["a"]["lexical_rank"] == 999  # solo vector
        assert by_id["b"]["vector_rank"] == 1
        assert by_id["b"]["lexical_rank"] == 0
        # a: 0.7*1.0 + 0.3*0 = 0.7; b: 0.7*0.4444 + 0.3*1.0 = 0.6111
        assert by_id["a"]["hybrid_score"] == pytest.approx(0.7)
        assert by_id["b"]["hybrid_score"] == pytest.approx(0.6111, abs=0.01)
        # orden por hybrid desc: a > b; k=2 excluye c
        assert res[0]["doc_id"] == "a"
        assert res[1]["doc_id"] == "b"
        assert res[0]["rank"] == 0
        assert res[1]["rank"] == 1

    def test_fusion_con_ceros(self) -> None:
        hr = HybridRetriever(
            _RetrieverStub([{"doc_id": "a", "score": 0.0, "rank": 0}]),
            _RetrieverStub([{"doc_id": "a", "score": 0.0, "rank": 0}]),
        )
        res = hr.search("q", k=5)
        assert len(res) == 1
        assert res[0]["hybrid_score"] == 0.0

    def test_vector_falla(self) -> None:
        hr = HybridRetriever(_RetrieverStub(fail=True), _RetrieverStub([{"doc_id": "x", "score": 1.0, "rank": 0}]))
        res = hr.search("q", k=5)
        assert len(res) == 1 and res[0]["doc_id"] == "x"

    def test_lexical_falla(self) -> None:
        hr = HybridRetriever(_RetrieverStub([{"doc_id": "x", "score": 1.0, "rank": 0}]), _RetrieverStub(fail=True))
        res = hr.search("q", k=5)
        assert len(res) == 1 and res[0]["doc_id"] == "x"

    def test_ambas_fallan(self) -> None:
        hr = HybridRetriever(_RetrieverStub(fail=True), _RetrieverStub(fail=True))
        assert hr.search("q", k=5) == []

    def test_limits_y_ranks(self) -> None:
        vec = _RetrieverStub([{"doc_id": f"d{i}", "score": float(i), "rank": i} for i in range(5)])
        lex = _RetrieverStub([])
        hr = HybridRetriever(vec, lex, alpha=1.0, beta=0.0)
        res = hr.search("q", k=2)
        assert len(res) == 2
        assert [r["rank"] for r in res] == [0, 1]


# ── reranking ───────────────────────────────────────────────────────────────


class TestRerankers:
    def test_noop(self) -> None:
        from motor.intelligence.reranking.noop import NoOpReranker

        cands = [{"doc_id": "a"}]
        assert NoOpReranker().rerank("q", cands) is cands

    def test_base_es_abstracta(self) -> None:
        from motor.intelligence.reranking.base import BaseReranker

        with pytest.raises(TypeError):
            BaseReranker()  # type: ignore[abstract]

    def test_ce_init_y_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)
        (tmp_path / "doc1.md").write_text("contenido de ejemplo", encoding="utf-8")
        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", top_k=5, batch_size=2)
        assert r._loaded is False
        assert r._doc_cache["doc1"] == "contenido de ejemplo"

    def test_ce_rerank(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)
        (tmp_path / "d1.md").write_text("primer documento", encoding="utf-8")

        class FakeToken:
            def __call__(self, batch: Any, **kw: Any) -> Any:
                return _FakeFeatures()

        class FakeModel:
            def __call__(self, **kw: Any) -> Any:
                return types.SimpleNamespace(
                    logits=types.SimpleNamespace(
                        squeeze=lambda *a: types.SimpleNamespace(
                            cpu=lambda: types.SimpleNamespace(numpy=lambda: types.SimpleNamespace(tolist=lambda: [0.8]))
                        )
                    )
                )

            def to(self, dev: Any) -> Any:
                return self

            def eval(self) -> Any:
                return self

        monkeypatch.setattr(ce.torch, "cuda", types.SimpleNamespace(is_available=lambda: False))
        monkeypatch.setattr(ce.torch, "no_grad", lambda: _CtxMgr())
        monkeypatch.setattr(ce, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda m: FakeToken()))
        monkeypatch.setattr(
            ce, "AutoModelForSequenceClassification", types.SimpleNamespace(from_pretrained=lambda m: FakeModel())
        )
        monkeypatch.setattr(ce.torch, "manual_seed", lambda *a: None)

        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", top_k=2)
        assert r.rerank("q", []) == []
        res = r.rerank("q", [{"doc_id": "d1", "rank": 0}])
        assert len(res) == 1
        assert res[0]["reranker_model"] == "fake"
        assert res[0]["reranker_score"] == pytest.approx(0.8)
        assert res[0]["rank"] == 0
        assert res[0]["score"] == pytest.approx(0.8)
        assert res[0]["reranker_latency_ms"] >= 0
        assert r._loaded is True
        assert r.rerank("q", [{"doc_id": "d1"}])[0]["reranker_score"] == pytest.approx(0.8)

    def test_ce_rerank_multi_batch_y_orden(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """3 candidatos con batch_size=2 → 2 batches, orden por score desc."""
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)
        for i, name in enumerate(("d1", "d2", "d3")):
            (tmp_path / f"{name}.md").write_text(f"documento {i}", encoding="utf-8")

        scores_iter = iter([[0.3, 0.9], [0.6]])

        class FakeToken:
            def __call__(self, batch: Any, **kw: Any) -> Any:
                return _FakeFeatures()

        class FakeModel:
            def __call__(self, **kw: Any) -> Any:
                batch_scores = next(scores_iter)
                return types.SimpleNamespace(
                    logits=types.SimpleNamespace(
                        squeeze=lambda *a: types.SimpleNamespace(
                            cpu=lambda: types.SimpleNamespace(
                                numpy=lambda: types.SimpleNamespace(tolist=lambda: batch_scores)
                            )
                        )
                    )
                )

            def to(self, dev: Any) -> Any:
                return self

            def eval(self) -> Any:
                return self

        monkeypatch.setattr(ce.torch, "cuda", types.SimpleNamespace(is_available=lambda: False))
        monkeypatch.setattr(ce.torch, "no_grad", lambda: _CtxMgr())
        monkeypatch.setattr(ce, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda m: FakeToken()))
        monkeypatch.setattr(
            ce, "AutoModelForSequenceClassification", types.SimpleNamespace(from_pretrained=lambda m: FakeModel())
        )

        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", top_k=3, batch_size=2)
        res = r.rerank("q", [{"doc_id": "d1"}, {"doc_id": "d2"}, {"doc_id": "d3"}])
        assert len(res) == 3
        # orden por score desc: d2 (0.9) > d3 (0.6) > d1 (0.3)
        assert [d["doc_id"] for d in res] == ["d2", "d3", "d1"]
        assert [d["rank"] for d in res] == [0, 1, 2]
        assert res[0]["reranker_score"] == pytest.approx(0.9)
        assert res[2]["reranker_score"] == pytest.approx(0.3)

    def test_ce_top_k_trunca(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """top_k=1 → solo re-rankea 1 candidato."""
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)
        (tmp_path / "d1.md").write_text("x", encoding="utf-8")
        (tmp_path / "d2.md").write_text("y", encoding="utf-8")

        class FakeToken:
            def __call__(self, batch: Any, **kw: Any) -> Any:
                return _FakeFeatures()

        class FakeModel:
            def __call__(self, **kw: Any) -> Any:
                return types.SimpleNamespace(
                    logits=types.SimpleNamespace(
                        squeeze=lambda *a: types.SimpleNamespace(
                            cpu=lambda: types.SimpleNamespace(numpy=lambda: types.SimpleNamespace(tolist=lambda: 0.5))
                        )
                    )
                )

            def to(self, dev: Any) -> Any:
                return self

            def eval(self) -> Any:
                return self

        monkeypatch.setattr(ce.torch, "cuda", types.SimpleNamespace(is_available=lambda: False))
        monkeypatch.setattr(ce.torch, "no_grad", lambda: _CtxMgr())
        monkeypatch.setattr(ce, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda m: FakeToken()))
        monkeypatch.setattr(
            ce, "AutoModelForSequenceClassification", types.SimpleNamespace(from_pretrained=lambda m: FakeModel())
        )

        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", top_k=1, batch_size=2)
        res = r.rerank("q", [{"doc_id": "d1"}, {"doc_id": "d2"}])
        assert len(res) == 1

    def test_ce_pares_exactos_al_tokenizer(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verifica que los pares (query, texto) que llegan al tokenizer son exactos."""
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)
        (tmp_path / "d1.md").write_text("contenido real del doc", encoding="utf-8")
        (tmp_path / "d2.md").write_text("otro contenido", encoding="utf-8")

        batches_recibidos: list[Any] = []

        class FakeToken:
            def __call__(self, batch: Any, **kw: Any) -> Any:
                batches_recibidos.append(batch)
                return _FakeFeatures()

        class FakeModel:
            def __call__(self, **kw: Any) -> Any:
                return types.SimpleNamespace(
                    logits=types.SimpleNamespace(
                        squeeze=lambda *a: types.SimpleNamespace(
                            cpu=lambda: types.SimpleNamespace(numpy=lambda: types.SimpleNamespace(tolist=lambda: [0.5, 0.5]))
                        )
                    )
                )

            def to(self, dev: Any) -> Any:
                return self

            def eval(self) -> Any:
                return self

        monkeypatch.setattr(ce.torch, "cuda", types.SimpleNamespace(is_available=lambda: False))
        monkeypatch.setattr(ce.torch, "no_grad", lambda: _CtxMgr())
        monkeypatch.setattr(ce, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda m: FakeToken()))
        monkeypatch.setattr(
            ce, "AutoModelForSequenceClassification", types.SimpleNamespace(from_pretrained=lambda m: FakeModel())
        )

        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", top_k=2, batch_size=2)
        r.rerank("mi query", [{"doc_id": "d1"}, {"doc_id": "d2"}])
        assert len(batches_recibidos) == 1
        assert batches_recibidos[0] == [("mi query", "contenido real del doc"), ("mi query", "otro contenido")]

    def test_ce_score_float_aislado(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path)

        class FakeToken:
            def __call__(self, batch: Any, **kw: Any) -> Any:
                return _FakeFeatures()

        class FakeModel:
            def __call__(self, **kw: Any) -> Any:
                return types.SimpleNamespace(
                    logits=types.SimpleNamespace(
                        squeeze=lambda *a: types.SimpleNamespace(
                            cpu=lambda: types.SimpleNamespace(numpy=lambda: types.SimpleNamespace(tolist=lambda: 0.42))
                        )
                    )
                )

            def to(self, dev: Any) -> Any:
                return self

            def eval(self) -> Any:
                return self

        monkeypatch.setattr(ce.torch, "no_grad", lambda: _CtxMgr())
        monkeypatch.setattr(ce, "AutoTokenizer", types.SimpleNamespace(from_pretrained=lambda m: FakeToken()))
        monkeypatch.setattr(
            ce, "AutoModelForSequenceClassification", types.SimpleNamespace(from_pretrained=lambda m: FakeModel())
        )
        r = ce.CrossEncoderReranker(model_name="fake", device="cpu", batch_size=5)
        r._lazy_load()
        scores = r._score_batch([("q", "t")])
        assert scores == [0.42]

    def test_llm_rerank(self, monkeypatch: pytest.MonkeyPatch) -> None:
        llm = _import_llm()
        monkeypatch.setattr(llm, "generate", lambda *a, **k: "8")

        r = llm.LLMReranker(model="m")
        assert r.rerank("q", []) == []
        res = r.rerank("q", [{"doc_id": "x", "payload": {"texto": "doc text"}}])
        assert len(res) == 1
        assert res[0]["reranker_score"] == 0.8
        assert res[0]["reranker_model"] == "m"

    def test_llm_via_cache(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        llm = _import_llm()
        monkeypatch.setattr(llm, "GOLDEN_DIR", tmp_path)
        monkeypatch.setattr(llm, "generate", lambda *a, **k: "5")
        (tmp_path / "d1.md").write_text("cacheado", encoding="utf-8")
        r = llm.LLMReranker(model="m")
        assert r._doc_cache["d1"] == "cacheado"
        res = r.rerank("q", [{"doc_id": "d1"}])
        assert res[0]["reranker_score"] == 0.5

    def test_llm_sin_texto(self) -> None:
        llm = _import_llm()
        r = llm.LLMReranker(model="m")
        res = r.rerank("q", [{"doc_id": "nope"}])
        assert res[0]["reranker_score"] == 0.0

    def test_llm_error_y_excepcion(self, monkeypatch: pytest.MonkeyPatch) -> None:
        llm = _import_llm()

        def boom(*a: Any, **k: Any) -> Any:
            raise RuntimeError("llm down")

        monkeypatch.setattr(llm, "generate", lambda *a, **k: "Error: modelo caido")
        assert llm.LLMReranker(model="m")._score("q", "d", "t") == 0.0
        monkeypatch.setattr(llm, "generate", boom)
        assert llm.LLMReranker(model="m")._score("q", "d", "t") == 0.0

    def test_llm_parse_score(self) -> None:
        llm = _import_llm()
        r = llm.LLMReranker()
        assert r._parse_score("7.5") == 0.75
        assert r._parse_score("12") == 1.0
        assert r._parse_score("sin numeros") == 0.0

    def test_llm_sin_golden_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        llm = _import_llm()
        monkeypatch.setattr(llm, "GOLDEN_DIR", tmp_path / "no_existe")
        monkeypatch.setattr(llm, "generate", lambda *a, **k: "8")
        r = llm.LLMReranker(model="m")
        assert r._doc_cache == {}
        assert r.rerank("q", [{"doc_id": "x", "payload": {"texto": "doc text"}}])[0]["reranker_score"] == 0.8

    def test_ce_sin_golden_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        ce = _import_ce()
        monkeypatch.setattr(ce, "GOLDEN_DIR", tmp_path / "no_existe")
        r = ce.CrossEncoderReranker(model_name="fake", device="cpu")
        assert r._doc_cache == {}


def _import_ce() -> types.ModuleType:
    if "motor.intelligence.reranking.ce" in sys.modules:
        return sys.modules["motor.intelligence.reranking.ce"]  # type: ignore[no-any-return]

    from motor.intelligence.reranking import ce

    return ce


def _import_llm() -> types.ModuleType:
    from motor.intelligence.reranking import llm

    return llm


# ── pipeline ────────────────────────────────────────────────────────────────


class TestPipeline:
    def test_enable_disable(self) -> None:
        disable_reranker()
        assert reranker_enabled() is False
        enable_reranker(_RetrieverStub([]))
        assert reranker_enabled() is True
        disable_reranker()
        assert reranker_enabled() is False

    def test_create_pipeline_defaults(self) -> None:
        hr = create_retrieval_pipeline()
        assert isinstance(hr, HybridRetriever)

    def test_create_pipeline_explicitos(self) -> None:
        vec = VectorRetriever(None)
        lex = LexicalRetriever("/tmp/ruta_que_no_existe_xyz")
        hr = create_retrieval_pipeline(vector_retriever=vec, lexical_retriever=lex, alpha=0.4, beta=0.6)
        assert hr._alpha == 0.4

    def test_search_sin_reranker(self) -> None:
        disable_reranker()
        hr = HybridRetriever(
            _RetrieverStub([{"doc_id": "a", "score": 1.0, "rank": 0}]),
            _RetrieverStub([]),
        )
        res = search_with_reranker("q", hr)
        assert res[0]["doc_id"] == "a"

    def test_search_con_reranker_ok(self) -> None:
        class _FakeReranker:
            def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
                return [dict(c, score=9.0) for c in candidates]

        enable_reranker(_FakeReranker())
        hr = HybridRetriever(
            _RetrieverStub([{"doc_id": "a", "score": 1.0, "rank": 0}]),
            _RetrieverStub([]),
        )
        res = search_with_reranker("q", hr)
        assert res[0]["score"] == 9.0
        disable_reranker()

    def test_search_con_reranker_falla(self) -> None:
        class _RerankerRoto:
            def rerank(self, query: str, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
                raise RuntimeError("rotura")

        enable_reranker(_RerankerRoto())
        hr = HybridRetriever(
            _RetrieverStub([{"doc_id": "a", "score": 1.0, "rank": 0}]),
            _RetrieverStub([]),
        )
        res = search_with_reranker("q", hr)
        assert res[0]["doc_id"] == "a"
        disable_reranker()
