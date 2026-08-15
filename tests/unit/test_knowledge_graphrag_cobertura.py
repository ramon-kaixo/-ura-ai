"""Cobertura 100x100 de knowledge/engine/graphrag.py (TASK-20260815-003).

Cubre el motor determinista GraphRAG: ranking heurístico (title/recency/
quality), los 4 stores con dobles (Asset, Memory, Lineage, Governance),
BFS de vecinos con detección de ciclos, dedup y ensamblado de ContextBundle.
dateutil no está instalado en el entorno: se inyecta un módulo fake en
sys.modules para cubrir ambas ramas try/except del cálculo de recency.
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from knowledge.engine import asset_store as asset_store_mod
from knowledge.engine import governance_store as governance_store_mod
from knowledge.engine import graphrag
from knowledge.engine import lineage_store as lineage_store_mod
from knowledge.engine import memory_store as memory_store_mod
from knowledge.engine.graphrag import (
    _DEFAULT_QUALITY as _default_quality,
)
from knowledge.engine.graphrag import (
    ContextBundle,
    RetrievalResult,
    SQLiteGraphRetriever,
    _compute_score,
)
from knowledge.engine.memory_store import MemoryRecord
from knowledge.engine.ontology.internal import AssetType, KnowledgeAsset

_WEIGHT_TITLE = graphrag._RANKING_WEIGHTS["title_match"]
_WEIGHT_QUALITY = graphrag._RANKING_WEIGHTS["quality"]
_WEIGHT_RECENCY = graphrag._RANKING_WEIGHTS["recency"]


def _fake_dateutil(monkeypatch: Any, dt: datetime | None = None, raise_error: bool = False) -> None:
    """Inyecta un dateutil fake en sys.modules para el cálculo de recency."""

    def parse(value: str) -> datetime:
        if raise_error:
            raise ValueError(f"bad date: {value}")
        return dt or datetime.now(UTC) - timedelta(days=1)

    monkeypatch.setitem(sys.modules, "dateutil", SimpleNamespace(parser=SimpleNamespace(parse=parse)))


class FakeAssetStore:
    """Doble de SQLiteAssetStore con cola configurable."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.assets: list[KnowledgeAsset] = []
        self.search_calls: list[tuple[str, int, AssetType | None]] = []

    def search_assets(self, query: str, limit: int = 10, asset_type: AssetType | None = None) -> list[KnowledgeAsset]:
        self.search_calls.append((query, limit, asset_type))
        return self.assets


class FakeMemoryStore:
    """Doble de SQLiteMemoryStore con cola configurable."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.records: list[MemoryRecord] = []
        self.search_calls: list[tuple[str, str | None, int]] = []

    def search(self, query: str, kind: str | None = None, limit: int = 10) -> list[MemoryRecord]:
        self.search_calls.append((query, kind, limit))
        return self.records


class FakeLineageStore:
    """Doble de SQLiteLineageStore con grafo configurable."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.upstream: dict[str, list[str]] = {}
        self.downstream: dict[str, list[str]] = {}
        self.events: list[dict[str, Any]] = []
        self.up_calls: list[str] = []
        self.down_calls: list[str] = []

    def get_upstream(self, asset_id: str) -> list[str]:
        self.up_calls.append(asset_id)
        return self.upstream.get(asset_id, [])

    def get_downstream(self, asset_id: str) -> list[str]:
        self.down_calls.append(asset_id)
        return self.downstream.get(asset_id, [])

    def get_lineage(self, asset_id: str) -> list[dict[str, Any]]:
        return self.events


class FakeGovernanceStore:
    """Doble de SQLiteGovernanceStore con políticas configurables."""

    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.policies: list[dict[str, Any]] = []
        self.calls: list[str] = []

    def get_policies(self, asset_id: str) -> list[dict[str, Any]]:
        self.calls.append(asset_id)
        return self.policies


def _asset(
    asset_id: str, title: str, quality: float = 0.9, updated_at: str = "", sha: str = "x" * 100
) -> KnowledgeAsset:
    return KnowledgeAsset(
        asset_id=asset_id,
        asset_type=AssetType.MARKDOWN,
        metadata={"title": title, "content_sha256": sha},
        quality=quality,
        updated_at=updated_at,
    )


def _memory(
    memory_id: str,
    title: str,
    kind: str = "note",
    content: str = "c" * 300,
    tags: tuple[str, ...] = ("t1",),
    related: tuple[str, ...] = ("a1",),
    updated_at: str = "",
    created_at: str = "",
) -> MemoryRecord:
    return MemoryRecord(
        memory_id=memory_id,
        kind=kind,
        title=title,
        content=content,
        tags=tags,
        related_assets=related,
        updated_at=updated_at,
        created_at=created_at,
    )


class RetrieverFixture:
    """Retriever con los 4 stores sustituidos por dobles."""

    def __init__(self, tmp_path: Path, monkeypatch: Any) -> None:
        self.asset_store = FakeAssetStore(tmp_path / "asset.sqlite")
        self.memory_store = FakeMemoryStore(tmp_path / "memory.sqlite")
        self.lineage_store = FakeLineageStore(tmp_path / "lineage.sqlite")
        self.governance_store = FakeGovernanceStore(tmp_path / "gov.sqlite")
        monkeypatch.setattr(asset_store_mod, "SQLiteAssetStore", lambda db: self.asset_store)
        monkeypatch.setattr(memory_store_mod, "SQLiteMemoryStore", lambda db: self.memory_store)
        monkeypatch.setattr(lineage_store_mod, "SQLiteLineageStore", lambda db: self.lineage_store)
        monkeypatch.setattr(governance_store_mod, "SQLiteGovernanceStore", lambda db: self.governance_store)
        self.retriever = SQLiteGraphRetriever(tmp_path / "db.sqlite")


class TestContextBundle:
    """ContextBundle: dataclass frozen y serialización a dict."""

    def test_to_dict_defaults(self) -> None:
        bundle = ContextBundle(query="q")
        data = bundle.to_dict()
        assert data["query"] == "q"
        assert data["assets"] == []
        assert data["memories"] == []
        assert data["stats"] == {
            "assets": 0,
            "memories": 0,
            "lineage": 0,
            "governance": 0,
            "neighbors": 0,
            "duration_ms": 0.0,
        }

    def test_to_dict_con_valores(self) -> None:
        bundle = ContextBundle(
            query="q",
            assets=[{"asset_id": "a1"}],
            memories=[{"memory_id": "m1"}],
            lineage=[{"asset_id": "a1"}],
            governance=[{"policy": "p"}],
            neighbors=[{"asset_id": "b1"}],
            total_duration_ms=1.5,
            asset_count=1,
            memory_count=1,
            lineage_count=1,
            governance_count=1,
            neighbor_count=1,
        )
        data = bundle.to_dict()
        assert data["assets"] == [{"asset_id": "a1"}]
        assert data["stats"]["duration_ms"] == 1.5
        assert data["stats"]["neighbors"] == 1

    def test_frozen(self) -> None:
        bundle = ContextBundle(query="q")
        with pytest.raises(AttributeError):
            bundle.query = "other"


class TestRetrievalResult:
    """RetrievalResult: dataclass con defaults."""

    def test_defaults(self) -> None:
        result = RetrievalResult(asset_id="a1", score=0.5)
        assert result.title == ""
        assert result.kind == ""
        assert result.snippet == ""
        assert result.metadata == {}

    def test_completo(self) -> None:
        result = RetrievalResult(
            asset_id="a1",
            score=0.9,
            title="t",
            kind="markdown",
            snippet="s",
            metadata={"k": "v"},
        )
        assert result.metadata == {"k": "v"}


class TestComputeScore:
    """_compute_score: ramas de title match, recency y quality."""

    def test_title_match_asset(self) -> None:
        score = _compute_score("graphrag", asset=_asset("a1", "GraphRAG architecture"))
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * 0.9)

    def test_sin_match_asset(self) -> None:
        score = _compute_score("zzz", asset=_asset("a1", "GraphRAG"))
        assert score == pytest.approx(_WEIGHT_QUALITY * 0.9)

    def test_title_match_memory(self) -> None:
        score = _compute_score("graphrag", memory=_memory("m1", "GraphRAG memory"))
        assert score > _WEIGHT_TITLE

    def test_memory_sin_atributos(self) -> None:
        score = _compute_score("graphrag", memory=SimpleNamespace(no_title=True))
        assert score == pytest.approx(_WEIGHT_QUALITY * _default_quality)

    def test_recency_success(self, monkeypatch: Any) -> None:
        _fake_dateutil(monkeypatch)
        asset = _asset("a1", "GraphRAG", updated_at="2026-08-14T10:00:00Z")
        score = _compute_score("graphrag", asset=asset)
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * 0.9 + _WEIGHT_RECENCY * (1 - 1 / 365))

    def test_recency_antiguo(self, monkeypatch: Any) -> None:
        _fake_dateutil(monkeypatch, dt=datetime.now(UTC) - timedelta(days=730))
        asset = _asset("a1", "GraphRAG", updated_at="2024-01-01T00:00:00Z")
        score = _compute_score("graphrag", asset=asset)
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * 0.9)

    def test_recency_error_parse(self, monkeypatch: Any) -> None:
        _fake_dateutil(monkeypatch, raise_error=True)
        asset = _asset("a1", "GraphRAG", updated_at="not-a-date")
        score = _compute_score("graphrag", asset=asset)
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * 0.9)

    def test_updated_vacio_asset(self) -> None:
        score = _compute_score("graphrag", asset=_asset("a1", "GraphRAG", updated_at=""))
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * 0.9)

    def test_created_at_fallback(self, monkeypatch: Any) -> None:
        _fake_dateutil(monkeypatch)
        memory = _memory("m1", "GraphRAG", updated_at="", created_at="2026-08-14T10:00:00Z")
        score = _compute_score("graphrag", memory=memory)
        assert score > _WEIGHT_TITLE

    def test_sin_dates_memory(self) -> None:
        memory = _memory("m1", "GraphRAG", updated_at="", created_at="")
        score = _compute_score("graphrag", memory=memory)
        assert score == pytest.approx(_WEIGHT_TITLE + _WEIGHT_QUALITY * _default_quality)

    def test_ni_asset_ni_memory(self) -> None:
        score = _compute_score("graphrag")
        assert score == pytest.approx(_WEIGHT_QUALITY * _default_quality)

    def test_title_sin_clave_metadata(self) -> None:
        asset = KnowledgeAsset(
            asset_id="a1",
            asset_type=AssetType.MARKDOWN,
            metadata={"content_sha256": "x"},
            quality=0.5,
            updated_at="",
        )
        score = _compute_score("graphrag", asset=asset)
        assert score == pytest.approx(_WEIGHT_QUALITY * 0.5)


class TestStoresLazy:
    """Carga perezosa de los 4 stores con caché."""

    def test_lazy_init_y_cache(self, tmp_path: Path, monkeypatch: Any) -> None:
        calls = {"asset": 0, "memory": 0, "lineage": 0, "gov": 0}

        def factory_asset(db: Path) -> FakeAssetStore:
            calls["asset"] += 1
            return FakeAssetStore(db)

        def factory_memory(db: Path) -> FakeMemoryStore:
            calls["memory"] += 1
            return FakeMemoryStore(db)

        def factory_lineage(db: Path) -> FakeLineageStore:
            calls["lineage"] += 1
            return FakeLineageStore(db)

        def factory_gov(db: Path) -> FakeGovernanceStore:
            calls["gov"] += 1
            return FakeGovernanceStore(db)

        monkeypatch.setattr(asset_store_mod, "SQLiteAssetStore", factory_asset)
        monkeypatch.setattr(memory_store_mod, "SQLiteMemoryStore", factory_memory)
        monkeypatch.setattr(lineage_store_mod, "SQLiteLineageStore", factory_lineage)
        monkeypatch.setattr(governance_store_mod, "SQLiteGovernanceStore", factory_gov)
        retriever = SQLiteGraphRetriever(tmp_path / "db.sqlite")

        retriever._get_asset_store()
        retriever._get_asset_store()
        retriever._get_memory_store()
        retriever._get_memory_store()
        retriever._get_lineage_store()
        retriever._get_lineage_store()
        retriever._get_governance_store()
        retriever._get_governance_store()

        assert calls == {"asset": 1, "memory": 1, "lineage": 1, "gov": 1}


class TestRetrieveAssets:
    """retrieve_assets: FTS5 con reordenamiento heurístico."""

    def test_ranking_y_recorte(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [
            _asset("a1", "GraphRAG architecture"),
            _asset("a2", "unrelated"),
        ]
        results = fx.retriever.retrieve_assets("graphrag", limit=1)
        assert [r.asset_id for r in results] == ["a1"]
        assert results[0].kind == "markdown"
        assert len(results[0].snippet) == 64
        assert fx.asset_store.search_calls == [("graphrag", 3, None)]

    def test_asset_type_passthrough(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [_asset("a1", "GraphRAG")]
        results = fx.retriever.retrieve_assets("graphrag", limit=10, asset_type=AssetType.PDF)
        assert len(results) == 1
        assert fx.asset_store.search_calls == [("graphrag", 30, AssetType.PDF)]

    def test_vacio(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assert fx.retriever.retrieve_assets("graphrag") == []

    def test_snippet_sin_sha(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        asset = _asset("a1", "GraphRAG", sha="short")
        fx.asset_store.assets = [asset]
        results = fx.retriever.retrieve_assets("graphrag")
        assert results[0].snippet == "short"


class TestRetrieveMemory:
    """retrieve_memory: búsqueda con metadatos de tags/related."""

    def test_con_kind(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.memory_store.records = [_memory("m1", "GraphRAG memory")]
        results = fx.retriever.retrieve_memory("graphrag", limit=10, kind="note")
        assert len(results) == 1
        assert results[0].asset_id == "m1"
        assert results[0].kind == "note"
        assert len(results[0].snippet) == 200
        assert results[0].metadata == {"tags": ["t1"], "related_assets": ["a1"]}
        assert fx.memory_store.search_calls == [("graphrag", "note", 20)]

    def test_sin_kind(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.memory_store.records = [_memory("m1", "GraphRAG memory")]
        results = fx.retriever.retrieve_memory("graphrag", limit=5)
        assert len(results) == 1
        assert fx.memory_store.search_calls == [("graphrag", None, 10)]

    def test_vacio(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assert fx.retriever.retrieve_memory("graphrag") == []


class TestRetrieveLineage:
    """retrieve_lineage: upstream/downstream/events en un dict."""

    def test_completo(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.upstream = {"a1": ["b1"]}
        fx.lineage_store.downstream = {"a1": ["c1"]}
        fx.lineage_store.events = [{"kind": "generated"}]
        result = fx.retriever.retrieve_lineage("a1")
        assert result == [{"asset_id": "a1", "upstream": ["b1"], "downstream": ["c1"], "events": 1}]

    def test_vacio(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        result = fx.retriever.retrieve_lineage("a1")
        assert result == [{"asset_id": "a1", "upstream": [], "downstream": [], "events": 0}]


class TestRetrieveGovernance:
    """retrieve_governance: políticas copiadas a dict."""

    def test_con_politicas(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.governance_store.policies = [{"policy": "p1"}, {"policy": "p2"}]
        assert fx.retriever.retrieve_governance("a1") == [{"policy": "p1"}, {"policy": "p2"}]
        assert fx.governance_store.calls == ["a1"]

    def test_vacio(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assert fx.retriever.retrieve_governance("a1") == []


class TestRetrieveNeighbors:
    """retrieve_neighbors: BFS con profundidad, ciclos y límites."""

    def test_depth_cero(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assert fx.retriever.retrieve_neighbors("a1", depth=0) == []

    def test_bfs_dos_niveles(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.upstream = {"a1": ["b1"], "b1": ["c1"]}
        fx.lineage_store.downstream = {"b1": ["a1"], "c1": ["b1"]}
        neighbors = fx.retriever.retrieve_neighbors("a1", depth=2)
        assert neighbors == [
            {"asset_id": "b1", "relation": "upstream", "depth": 1},
            {"asset_id": "c1", "relation": "upstream", "depth": 2},
        ]

    def test_ciclo_y_visited(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.upstream = {"a1": ["b1"], "b1": ["c1"], "c1": ["a1"]}
        fx.lineage_store.downstream = {"b1": ["a1"]}
        neighbors = fx.retriever.retrieve_neighbors("a1", depth=3)
        ids = [n["asset_id"] for n in neighbors]
        assert ids == ["b1", "c1"]
        assert ids.count("a1") == 0

    def test_max_nodes_break_up(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.upstream = {"a1": ["u1", "u2"]}
        neighbors = fx.retriever.retrieve_neighbors("a1", depth=2, max_nodes=1)
        assert neighbors == [{"asset_id": "u1", "relation": "upstream", "depth": 1}]

    def test_max_nodes_break_down(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.downstream = {"a1": ["d1", "d2"]}
        neighbors = fx.retriever.retrieve_neighbors("a1", depth=2, max_nodes=1)
        assert neighbors == [{"asset_id": "d1", "relation": "downstream", "depth": 1}]

    def test_enqueue_down(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.lineage_store.downstream = {"a1": ["d1"]}
        neighbors = fx.retriever.retrieve_neighbors("a1", depth=2)
        assert neighbors == [{"asset_id": "d1", "relation": "downstream", "depth": 1}]

    def test_sin_vecinos(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assert fx.retriever.retrieve_neighbors("a1", depth=2) == []


class TestContextoGrafo:
    """_contexto_grafo: top-3, flags de inclusión y dedup."""

    def test_top_tres(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assets = [_asset(f"a{i}", "GraphRAG") for i in range(4)]
        calls: list[str] = []
        original = fx.retriever.retrieve_lineage

        def wrap(aid: str) -> list[dict[str, Any]]:
            calls.append(aid)
            return original(aid)

        monkeypatch.setattr(fx.retriever, "retrieve_lineage", wrap)
        lineage, governance, neighbors = fx.retriever._contexto_grafo(assets, True, True, 0)
        assert calls == ["a0", "a1", "a2"]
        assert [entry["asset_id"] for entry in lineage] == ["a0", "a1", "a2"]
        assert governance == []
        assert neighbors == []

    def test_sin_flags(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assets = [_asset("a0", "GraphRAG")]
        lineage, governance, neighbors = fx.retriever._contexto_grafo(assets, False, False, 0)
        assert lineage == []
        assert governance == []
        assert neighbors == []
        assert fx.lineage_store.up_calls == []
        assert fx.governance_store.calls == []

    def test_dedup_vecinos(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        assets = [_asset("a0", "GraphRAG")]
        monkeypatch.setattr(
            fx.retriever,
            "retrieve_neighbors",
            lambda aid, depth=2, max_nodes=100: [
                {"asset_id": "x1", "relation": "upstream", "depth": 1},
                {"asset_id": "x1", "relation": "upstream", "depth": 1},
            ],
        )
        _, _, neighbors = fx.retriever._contexto_grafo(assets, False, False, 2)
        assert neighbors == [{"asset_id": "x1", "relation": "upstream", "depth": 1}]


class TestBuildContext:
    """build_context: ensamblado completo del ContextBundle."""

    def test_completo(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [_asset("a1", "GraphRAG architecture")]
        fx.memory_store.records = [_memory("m1", "GraphRAG memory")]
        fx.lineage_store.upstream = {"a1": ["b1"]}
        fx.governance_store.policies = [{"policy": "p1"}]
        bundle = fx.retriever.build_context("graphrag", neighbor_depth=1)
        assert bundle.query == "graphrag"
        assert bundle.asset_count == 1
        assert bundle.memory_count == 1
        assert bundle.lineage_count == 1
        assert bundle.governance_count == 1
        assert bundle.neighbor_count == 1
        assert bundle.assets[0]["asset_id"] == "a1"
        assert bundle.memories[0]["memory_id"] == "m1"
        assert bundle.lineage[0]["asset_id"] == "a1"
        assert bundle.governance[0]["policy"] == "p1"
        assert bundle.neighbors[0]["asset_id"] == "b1"
        assert bundle.total_duration_ms >= 0
        assert bundle.to_dict()["stats"]["assets"] == 1

    def test_sin_lineage_ni_governance(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [_asset("a1", "GraphRAG")]
        bundle = fx.retriever.build_context("graphrag", include_lineage=False, include_governance=False)
        assert bundle.lineage == []
        assert bundle.governance == []
        assert fx.lineage_store.up_calls == []
        assert fx.governance_store.calls == []

    def test_sin_vecinos(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [_asset("a1", "GraphRAG")]
        bundle = fx.retriever.build_context("graphrag", neighbor_depth=0)
        assert bundle.neighbors == []
        assert bundle.neighbor_count == 0

    def test_vacio(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        bundle = fx.retriever.build_context("graphrag")
        assert bundle.asset_count == 0
        assert bundle.memory_count == 0
        assert bundle.lineage == []
        assert bundle.governance == []
        assert bundle.neighbors == []

    def test_top_memories_limit(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.memory_store.records = [_memory(f"m{i}", "GraphRAG memory") for i in range(6)]
        bundle = fx.retriever.build_context("graphrag", max_memories=2)
        assert bundle.memory_count == 2
        assert fx.memory_store.search_calls == [("graphrag", None, 4)]


class TestSerializers:
    """_serializar_assets y _serializar_memorias vía build_context."""

    def test_serializacion(self, tmp_path: Path, monkeypatch: Any) -> None:
        fx = RetrieverFixture(tmp_path, monkeypatch)
        fx.asset_store.assets = [_asset("a1", "GraphRAG")]
        fx.memory_store.records = [_memory("m1", "GraphRAG memory")]
        bundle = fx.retriever.build_context("graphrag")
        assert bundle.assets == [
            {
                "asset_id": "a1",
                "score": bundle.assets[0]["score"],
                "title": "GraphRAG",
                "kind": "markdown",
                "snippet": "x" * 64,
            }
        ]
        assert bundle.memories[0]["memory_id"] == "m1"
        assert bundle.memories[0]["metadata"] == {"tags": ["t1"], "related_assets": ["a1"]}
