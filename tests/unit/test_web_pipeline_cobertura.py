"""Cobertura 100x100 de motor/core/web/pipeline.py (TASK-20260815-003).

Cubre WebPipeline.search (con fuentes explícitas, default, KeyError skip),
fetch, extract, clean (DocumentCleaner + DeduplicationEngine reales),
rank, rank_documents y summarize_documents (rankers/summarizers reales),
cite (CitationEngine real), summarize (registry), run (flujo completo,
sin extract/summarize, error de fetch, sin documentos) y persist (docs
vacíos, éxito F25, error del pipeline de fusión, error por fact).

Sin llamadas de red: registry y dependencias externas mockeadas; los
components internos (cleaner, ranker, summarizer, citation) son reales.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from motor.core.web.models import Citation, SearchResult, WebDocument
from motor.core.web.pipeline import PipelineStage, WebPipeline
from motor.core.web.summarizer.summarizer import Summary


class _FakeRegistry:
    """Registry simulado con proveedores inyectables."""

    def __init__(self) -> None:
        self.searchers: dict[str, Any] = {}
        self.crawlers: dict[str, Any] = {}
        self.extractors: dict[str, Any] = {}
        self.rankers: dict[str, Any] = {}
        self.summarizers: dict[str, Any] = {}

    def list_searchers(self) -> list[str]:
        return list(self.searchers)

    def get_searcher(self, name: str) -> Any:
        return self.searchers[name]

    def get_crawler(self, name: str) -> Any:
        return self.crawlers[name]

    def get_extractor(self, name: str) -> Any:
        return self.extractors[name]

    def get_ranker(self, name: str) -> Any:
        return self.rankers[name]

    def get_summarizer(self, name: str) -> Any:
        return self.summarizers[name]


def _result(url: str = "https://example.com/a") -> SearchResult:
    return SearchResult(title="T", url=url, snippet="S", source="s")


def _document(url: str = "https://example.com/a", text: str = "") -> WebDocument:
    return WebDocument(
        url=url,
        title="T",
        text=text or "Este es el contenido completo de un documento web de ejemplo para pruebas.",
        word_count=10,
    )


def _make_registry() -> _FakeRegistry:
    registry = _FakeRegistry()

    def searcher(q: str, limit: int = 10) -> list[SearchResult]:
        return [_result()]

    registry.searchers["ddg"] = SimpleNamespace(search=searcher, name="ddg")
    registry.crawlers["httpx"] = SimpleNamespace(
        fetch=lambda url: "<html><body><p>hola</p></body></html>",
        name="httpx",
    )
    registry.extractors["readability"] = SimpleNamespace(
        extract=lambda html, url: _document(url=url),
        name="readability",
    )
    registry.rankers["default"] = SimpleNamespace(
        rank=lambda results, query: list(results),
        name="default",
    )
    registry.summarizers["llm"] = SimpleNamespace(
        summarize=lambda query, documents: ("Resumen.", [Citation(text="C", url=doc.url, title="T", source="s") for doc in documents]),
        name="llm",
    )
    return registry


class TestSearch:
    """Búsqueda."""

    def test_busqueda_con_fuentes(self) -> None:
        registry = _make_registry()
        p = WebPipeline(registry)
        results = p.search("q", sources=["ddg"])
        assert len(results) == 1
        assert PipelineStage.SEARCH in p._stage_times

    def test_busqueda_sin_fuentes_usa_registry(self) -> None:
        registry = _make_registry()
        p = WebPipeline(registry)
        results = p.search("q")
        assert len(results) == 1

    def test_busqueda_keyerror_salta_fuente(self) -> None:
        class _RegistryConFallos:
            def list_searchers(self) -> list[str]:
                return ["rota", "buena"]

            def get_searcher(self, name: str) -> Any:
                if name == "rota":
                    raise KeyError(name)
                return SimpleNamespace(search=lambda q, limit=10: [_result()])

        p = WebPipeline(_RegistryConFallos())
        results = p.search("q")
        assert len(results) == 1

    def test_busqueda_vacia(self) -> None:
        registry = _make_registry()
        registry.searchers = {}  # type: ignore[assignment]
        p = WebPipeline(registry)
        assert p.search("q") == []

    def test_fetch(self) -> None:
        p = WebPipeline(_make_registry())
        html = p.fetch("https://example.com/a")
        assert "hola" in html
        assert PipelineStage.CRAWL in p._stage_times

    def test_extract(self) -> None:
        p = WebPipeline(_make_registry())
        doc = p.extract("<html></html>", "https://example.com/a")
        assert doc.url == "https://example.com/a"
        assert PipelineStage.EXTRACT in p._stage_times


class TestClean:
    """Limpieza y deduplicación."""

    def test_clean(self) -> None:
        p = WebPipeline(_make_registry())
        cleaned = p.clean([_document()])
        assert len(cleaned.documents) == 1
        assert PipelineStage.CLEAN in p._stage_times

    def test_clean_dedup_y_vacias(self) -> None:
        p = WebPipeline(_make_registry())
        cleaned = p.clean([_document(), _document(), _document(text="")])
        # HALLAZGO: el pipeline deduplica por URL ANTES del filtro de vacíos:
        # los 3 comparten URL → 2 removed_duplicate_url y 0 removed_empty
        # (el doc vacío se cuenta como duplicado, no como vacío).
        assert len(cleaned.documents) == 1
        assert cleaned.stats.documents_removed_empty == 0
        assert cleaned.stats.documents_removed_duplicate_url == 2

    def test_clean_rdeduplica_por_contenido(self) -> None:
        p = WebPipeline(_make_registry())
        a = _document(url="https://example.com/a")
        b = WebDocument(url="https://example.com/b", title="T", text=a.text, word_count=10)
        cleaned = p.clean([a, b])
        assert len(cleaned.documents) == 1

    def test_clean_min_words(self) -> None:
        p = WebPipeline(_make_registry())
        cleaned = p.clean([_document(text="corto")], min_words=5)
        assert cleaned.documents == []


class TestRank:
    """Ranking."""

    def test_rank_usa_registry(self) -> None:
        registry = _make_registry()
        p = WebPipeline(registry)
        results = [SearchResult(title="T", url="https://example.com/a", snippet="S", source="s")]
        ranked = p.rank(results, "q")
        assert list(ranked) == results
        assert PipelineStage.RANK in p._stage_times

    def test_rank_documents_real(self) -> None:
        p = WebPipeline(_make_registry())
        ranked = p.rank_documents("python", [_document(text="python es un lenguaje de programación usado y popular")])
        assert len(ranked) == 1
        assert ranked[0].document.url == "https://example.com/a"
        assert PipelineStage.RANK in p._stage_times

    def test_rank_documents_sin_posiciones(self) -> None:
        p = WebPipeline(_make_registry())
        ranked = p.rank_documents("q", [_document()])
        assert len(ranked) == 1


class TestSummarize:
    """Resumen extractivo y vía registry."""

    def test_summarize_documents_reales(self) -> None:
        p = WebPipeline(_make_registry())
        summary: Summary = p.summarize_documents([_document(text="Primera frase del documento. Segunda frase.")])
        assert summary.sentences
        assert PipelineStage.SUMMARIZE in p._stage_times

    def test_summarize_via_registry(self) -> None:
        p = WebPipeline(_make_registry())
        summary, citations = p.summarize("q", [_document()])
        assert summary == "Resumen."
        assert len(citations) == 1
        assert PipelineStage.SUMMARIZE in p._stage_times

    def test_cite(self) -> None:
        p = WebPipeline(_make_registry())
        doc = _document()
        summary = Summary(
            text="Frase.",
            sentences=["Frase."],
            source_documents=[doc.url],
            sentence_origins=[{"url": doc.url, "title": "T", "position": 0}],
            compression_ratio=0.0,
        )
        bundle = p.cite(summary, [doc])
        assert len(bundle.citations) == 1
        assert bundle.evidence[0].document_url == doc.url
        assert PipelineStage.VALIDATE in p._stage_times


class TestRun:
    """Pipeline completo."""

    def test_run_completo(self) -> None:
        p = WebPipeline(_make_registry())
        result = p.run("q", limit=10)
        assert result["query"] == "q"
        assert result["search_results"][0]["url"] == "https://example.com/a"
        assert len(result["results"]) == 1
        assert result["summary"] == "Resumen."
        assert len(result["citations"]) == 1
        assert result["elapsed_ms"] >= 0
        assert "search" in result["stage_times"]

    def test_run_sin_extract_ni_summarize(self) -> None:
        p = WebPipeline(_make_registry())
        result = p.run("q", extract=False, summarize=False)
        assert result["results"] == []
        assert result["summary"] is None
        assert result["citations"] == []
        assert result["elapsed_ms"] >= 0
        assert "search" in result["stage_times"]

    def test_run_error_fetch_se_ignora(self) -> None:
        registry = _make_registry()

        def _crawl_roto(url: str, timeout: int = 30) -> str:
            raise RuntimeError("net")

        registry.crawlers["httpx"] = SimpleNamespace(fetch=_crawl_roto, name="httpx")
        p = WebPipeline(registry)
        result = p.run("q")
        assert result["results"] == []
        assert result["summary"] is None

    def test_run_sin_documentos_no_resume(self) -> None:
        registry = _make_registry()

        def searcher(q: str, limit: int = 10) -> list[SearchResult]:
            return []

        registry.searchers["ddg"] = SimpleNamespace(search=searcher, name="ddg")
        p = WebPipeline(registry)
        result = p.run("q")
        assert result["results"] == []
        assert result["summary"] is None


class TestPersist:
    """Ingesta web → memoria semántica (F25)."""

    def _patch_fusion(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        accepted: list[Any],
        run_error: Exception | None = None,
    ) -> None:
        import motor.core.fusion.bridge
        import motor.core.fusion.engine
        import motor.intelligence.memory.semantic

        class _Engine:
            @staticmethod
            def default() -> _Run:
                return _Run()

        class _Run:
            def run(self, bundle: Any, documents: list[Any]) -> Any:
                if run_error is not None:
                    raise run_error
                return SimpleNamespace(accepted=accepted)

        def _convert(kf: Any) -> dict[str, Any]:
            return {"text": f"text-{kf}"}

        class _Fact:
            def __init__(self, **kwargs: dict[str, Any]) -> None:
                self.kwargs = kwargs

        monkeypatch.setattr(motor.core.fusion.engine, "FusionPipeline", _Engine)
        monkeypatch.setattr(motor.core.fusion.bridge, "knowledge_fact_to_semantic_fact", _convert)
        monkeypatch.setattr(motor.intelligence.memory.semantic, "SemanticFact", _Fact)

    def test_persist_sin_documentos(self) -> None:
        p = WebPipeline(_make_registry())
        assert p.persist([], store=object()) == {"stored": 0, "errors": []}

    def test_persist_exito(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_fusion(monkeypatch, accepted=["kf1", "kf2"])
        records: list[Any] = []

        class _Store:
            def store(self, sf: Any) -> None:
                records.append(sf)

        p = WebPipeline(_make_registry())
        result = p.persist([_document()], store=_Store())
        assert result == {"stored": 2, "errors": []}
        assert records[0].kwargs == {"text": "text-kf1"}
        # evidence_id/position/document_hash cubiertos por _convert

    def test_persist_error_pipeline(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch_fusion(monkeypatch, accepted=[], run_error=RuntimeError("fusion fallo"))
        p = WebPipeline(_make_registry())
        result = p.persist([_document()], store=object())
        assert result["stored"] == 0
        assert len(result["errors"]) == 1
        assert "fusion fallo" in result["errors"][0]

    def test_persist_error_por_fact(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import motor.core.fusion.bridge
        import motor.core.fusion.engine
        import motor.intelligence.memory.semantic

        class _Engine:
            @staticmethod
            def default() -> _Run:
                return _Run()

        class _Run:
            def run(self, bundle: Any, documents: list[Any]) -> Any:
                return SimpleNamespace(accepted=["kf1", "kf2"])

        def _convert(kf: Any) -> dict[str, Any]:
            if kf == "kf1":
                raise ValueError(f"no convertible {kf}")
            return {"text": f"text-{kf}"}

        class _Fact:
            def __init__(self, **kwargs: Any) -> None:
                self.kwargs = kwargs

        class _Store:
            def store(self, sf: Any) -> None:
                return None

        monkeypatch.setattr(motor.core.fusion.engine, "FusionPipeline", _Engine)
        monkeypatch.setattr(motor.core.fusion.bridge, "knowledge_fact_to_semantic_fact", _convert)
        monkeypatch.setattr(motor.intelligence.memory.semantic, "SemanticFact", _Fact)

        p = WebPipeline(_make_registry())
        result = p.persist([_document()], store=_Store())
        assert result["stored"] == 1
        assert len(result["errors"]) == 1
        assert "no convertible" in result["errors"][0]


class TestRegistryProperty:
    """Acceso al registry."""

    def test_self_registry(self) -> None:
        registry = _make_registry()
        assert WebPipeline(registry).registry is registry

    def test_stage_times_init(self) -> None:
        assert WebPipeline(_make_registry())._stage_times == {}
