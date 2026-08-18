"""Tests de deduction del knowledge engine (StateDeductor).

Cobertura de knowledge/engine/deduction.py: _contar, deduce,
_deducir_huerfanos, _deducir_cobertura y _deducir_hubs contra el
contrato real del modulo (TASK-20260818-029).
"""

from __future__ import annotations

from typing import Any

from knowledge.engine.deduction import StateDeductor


def get_sample_data() -> dict[str, list[dict[str, Any]]]:
    """15 nodos (types 0/1/2 para i<9, 'unknown' para el resto) + 8 references + 8 requires."""
    nodes: list[dict[str, Any]] = [
        {"id": f"n{i}", "type": str(i % 3) if i < 9 else "unknown"} for i in range(15)
    ]
    edges: list[dict[str, Any]] = [
        {"src": f"n{i}", "dst": f"n{(i + 1) % 8}", "relation": "references"} for i in range(8)
    ] + [
        {"src": f"n{i}", "dst": "hub_node", "relation": "requires"} for i in range(7, 15)
    ]
    return {"nodes": nodes, "edges": edges}


class TestDeduction:
    def test_contar(self) -> None:
        nodes = [
            {"id": "a", "type": "guide"},
            {"id": "b", "type": "reference"},
            {"id": "c", "type": "guide"},
        ]
        edges = [{"src": "a", "dst": "b"}, {"src": "b", "dst": "c"}]
        type_counts, src_counts, dst_counts = StateDeductor()._contar(nodes, edges)
        assert dict(type_counts) == {"guide": 2, "reference": 1}
        assert dict(src_counts) == {"a": 1, "b": 1}
        assert dict(dst_counts) == {"b": 1, "c": 1}

    def test_huerfanos(self) -> None:
        sample = get_sample_data()
        refs_only = [e for e in sample["edges"] if e["relation"] == "references"]
        data = StateDeductor().deduce(sample["nodes"], refs_only)
        orphans = [d for d in data if d.kind == "orphan"]
        assert len(orphans) == 7  # n8..n14 sin edges (hub_node no esta en nodes)
        assert all("Documento sin relaciones" in d.description for d in orphans)

    def test_cobertura(self) -> None:
        sample = get_sample_data()
        data = StateDeductor().deduce(sample["nodes"], [])
        coverage = [d for d in data if d.kind == "coverage"]
        assert len(coverage) == 4  # types 0, 1, 2 y 'unknown'
        expected = {"0": 3, "1": 3, "2": 3, "unknown": 6}
        for d in coverage:
            assert d.subject_id in expected
            assert d.metadata["count"] == expected[d.subject_id]
            assert abs(d.metadata["ratio"] - expected[d.subject_id] / 15) < 0.01

    def test_hubs(self) -> None:
        sample = get_sample_data()
        data = StateDeductor().deduce(sample["nodes"], sample["edges"])
        hubs = [d for d in data if d.kind == "dependency" and d.subject_id == "hub_node"]
        assert len(hubs) == 1
        h = hubs[0]
        assert h.metadata["inbound_refs"] == 8
        assert h.confidence == 1.0