"""Tests de cobertura para knowledge/engine/deduction.py."""

from __future__ import annotations

from knowledge.engine.deduction import Deduction, StateDeductor


def _node(nid: str, dtype: str = "doc", path: str | None = None) -> dict:
    return {"id": nid, "type": dtype, "path": path or f"docs/{nid}.md"}


def _edge(src: str, dst: str) -> dict:
    return {"src": src, "dst": dst, "relation": "references"}


def test_deduce_huerfano() -> None:
    results = StateDeductor().deduce([_node("a1")], [])
    orphans = [r for r in results if r.kind == "orphan"]
    assert len(orphans) == 1
    o = orphans[0]
    assert o.subject_id == "a1"
    assert o.confidence == 0.9
    assert o.metadata["type"] == "doc"


def test_deduce_no_huerfano_si_tiene_edges() -> None:
    results = StateDeductor().deduce([_node("a1"), _node("a2")], [_edge("a1", "a2")])
    assert [r for r in results if r.kind == "orphan"] == []


def test_deduce_cobertura() -> None:
    nodes = [_node("a1", "doc"), _node("a2", "doc"), _node("b1", "spec")]
    results = StateDeductor().deduce(nodes, [])
    covers = {r.subject_id: r for r in results if r.kind == "coverage"}
    assert covers["doc"].metadata["count"] == 2
    assert covers["doc"].metadata["ratio"] == 2 / 3
    assert covers["spec"].metadata["count"] == 1
    assert covers["spec"].confidence == 1.0


def test_deduce_cobertura_vacio() -> None:
    assert StateDeductor().deduce([], []) == []


def test_deduce_hubs() -> None:
    nodes = [_node("hub"), _node("x1"), _node("x2"), _node("x3")]
    edges = [_edge("x1", "hub"), _edge("x2", "hub"), _edge("x3", "hub"), _edge("x1", "x2")]
    results = StateDeductor().deduce(nodes, edges)
    hubs = [r for r in results if r.kind == "dependency"]
    assert len(hubs) == 1
    h = hubs[0]
    assert h.subject_id == "hub"
    assert h.metadata["inbound_refs"] == 3
    assert h.confidence == 1.0


def test_deduce_hub_unica_referencia_no() -> None:
    nodes = [_node("hub"), _node("x1")]
    results = StateDeductor().deduce(nodes, [_edge("x1", "hub")])
    assert [r for r in results if r.kind == "dependency"] == []


def test_deduce_sin_edges_no_hubs() -> None:
    results = StateDeductor().deduce([_node("a1")], [])
    assert [r for r in results if r.kind == "dependency"] == []


def test_deduce_hub_sin_nodo_registrado() -> None:
    results = StateDeductor().deduce([_node("x1"), _node("x2")], [_edge("x1", "fantasma"), _edge("x2", "fantasma")])
    hubs = [r for r in results if r.kind == "dependency"]
    assert len(hubs) == 1
    assert hubs[0].subject_id == "fantasma"
    assert hubs[0].metadata["path"] == ""


def test_contar() -> None:
    type_counts, src_counts, dst_counts = StateDeductor()._contar(
        [_node("a1"), _node("a2", "spec")],
        [_edge("a1", "a2")],
    )
    assert type_counts["doc"] == 1
    assert type_counts["spec"] == 1
    assert type_counts["unknown"] == 0
    assert src_counts["a1"] == 1
    assert dst_counts["a2"] == 1


def test_contar_sin_tipo() -> None:
    type_counts, _, _ = StateDeductor()._contar([{"id": "x"}], [])
    assert type_counts["unknown"] == 1


def test_deduccion_dataclass() -> None:
    d = Deduction(kind="coverage", subject_id="doc", description="d", confidence=0.5, metadata={"k": 1})
    assert d.metadata["k"] == 1
    assert d.confidence == 0.5
