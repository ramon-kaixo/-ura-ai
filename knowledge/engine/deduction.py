"""StateDeductor — deduce estado implícito del grafo de conocimiento.

A partir de las relaciones y tipos de nodos, infiere:
  - Estado de documentos (actualizado, desactualizado, huérfano)
  - Cobertura de temas (qué áreas están cubiertas, cuáles faltan)
  - Dependencias entre documentos (qué documentos referencian a otros)

Principios:
  - Solo lectura de kg_*. Nunca escribe.
  - Deducciones en memoria (overlay), no persistentes.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("ura.knowledge.deduction")


@dataclass(frozen=True)
class Deduction:
    """Una deducción de estado sobre el grafo."""

    kind: str  # "coverage" | "dependency" | "staleness" | "orphan"
    subject_id: str
    description: str
    confidence: float  # 0.0 - 1.0
    metadata: dict[str, Any] = field(default_factory=dict)


class StateDeductor:
    """Deduce estado del grafo de conocimiento.

    Uso:
        deductor = StateDeductor()
        deductions = deductor.deduce(nodes, edges)
    """

    def deduce(
        self,
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
    ) -> list[Deduction]:
        """Deduce estado a partir de nodos y edges del grafo.

        Args:
            nodes: Lista de nodos como dicts con id, type, path, etc.
            edges: Lista de edges como dicts con src, dst, relation.

        Returns:
            Lista de deducciones.

        """
        results: list[Deduction] = []
        node_map = {n["id"]: n for n in nodes}
        type_counts: Counter[str] = Counter()
        src_counts: Counter[str] = Counter()
        dst_counts: Counter[str] = Counter()

        for n in nodes:
            type_counts[n.get("type", "unknown")] += 1

        for e in edges:
            src_counts[e["src"]] += 1
            dst_counts[e["dst"]] += 1

        # 1. Documentos huérfanos (sin relaciones entrantes ni salientes)
        for n in nodes:
            nid = n["id"]
            if src_counts.get(nid, 0) == 0 and dst_counts.get(nid, 0) == 0:
                results.append(
                    Deduction(
                        kind="orphan",
                        subject_id=nid,
                        description=f"Documento sin relaciones: {n.get('path', nid)}",
                        confidence=0.9,
                        metadata={"type": n.get("type", "")},
                    ),
                )

        # 2. Cobertura por tipo
        if nodes:
            total = len(nodes)
            for dtype, count in sorted(type_counts.items()):
                coverage = count / total
                results.append(
                    Deduction(
                        kind="coverage",
                        subject_id=dtype,
                        description=f"Cobertura {dtype}: {count}/{total} ({coverage:.0%})",
                        confidence=1.0,
                        metadata={"count": count, "total": total, "ratio": coverage},
                    ),
                )

        # 3. Documentos más referenciados (hub nodes)
        if dst_counts:
            max_refs = max(dst_counts.values())
            threshold = max(max_refs * 0.5, 1)
            for nid, refs in dst_counts.items():
                if refs >= threshold and refs > 1:
                    node = node_map.get(nid, {})
                    results.append(
                        Deduction(
                            kind="dependency",
                            subject_id=nid,
                            description=f"Nodo central: {refs} referencias entrantes",
                            confidence=min(refs / max_refs, 1.0),
                            metadata={
                                "inbound_refs": refs,
                                "path": node.get("path", ""),
                            },
                        ),
                    )

        return results
