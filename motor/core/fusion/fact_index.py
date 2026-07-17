"""FactIndex — índice de hechos (R06, F25-B4/B6).

Soporta tanto KnowledgeFact (legacy) como Fact+FactVersion (nuevo modelo).
FactIndex indexa solo la versión vigente. Histórico via FactHistory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.fusion.models import Fact, FactVersion, KnowledgeFact


class FactIndex:
    """Índice de hechos con índices secundarios.

    Soporta dos modos:
    - Legacy: add_fact(KnowledgeFact) — índices por subject/predicate
    - Nuevo: add_fact_version(Fact, FactVersion) — índices por Fact.subject/predicate

    Índices mantenidos (todos O(1) amortizado):
    - fact_id → fact (KnowledgeFact o tuple[Fact, FactVersion])
    - entity (subject) → ordered set[fact_id]
    - predicate → ordered set[fact_id]
    - (subject, predicate) → ordered set[fact_id]
    - evidence_id → ordered set[fact_id]

    Concurrencia:
    - Lecturas concurrentes: seguras (dict.get atómico en CPython).
    - Escrituras: deben serializarse externamente.
    - build() → freeze() → swap referencia.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, Any] = {}
        self._by_entity: dict[str, dict[str, None]] = {}
        self._by_predicate: dict[str, dict[str, None]] = {}
        self._by_sp: dict[tuple[str, str], dict[str, None]] = {}
        self._by_evidence: dict[str, dict[str, None]] = {}
        self._frozen: bool = False

    # ── API pública (legacy) ──────────────────────────

    def add_fact(self, fact: KnowledgeFact) -> None:
        """Indexa un KnowledgeFact (legacy)."""
        self._check_mutable()
        fid, subj, pred, eids = fact.id, fact.subject, fact.predicate, fact.evidence_ids
        self._add(fid, fact, subj, pred, eids)

    def remove_fact(self, fact_id: str) -> Any:
        """Elimina un fact del índice."""
        self._check_mutable()
        fact = self._by_id.pop(fact_id, None)
        if fact is None:
            raise KeyError(f"Fact '{fact_id}' not found")

        subj, pred, eids = self._extract_keys(fact)
        self._remove_from_ordered_set(self._by_entity, subj.lower(), fact_id)
        self._remove_from_ordered_set(self._by_predicate, pred.lower(), fact_id)
        self._remove_from_ordered_set(self._by_sp, (subj.lower(), pred.lower()), fact_id)
        for eid in eids:
            if eid:
                self._remove_from_ordered_set(self._by_evidence, eid, fact_id)
        return fact

    # ── API pública (nuevo modelo) ────────────────────

    def add_fact_version(self, fact: Fact, version: FactVersion) -> None:
        """Indexa un Fact con su versión vigente.

        Solo la versión vigente se indexa. Histórico via FactHistory.
        """
        self._check_mutable()
        fid = fact.fact_id
        if fid in self._by_id:
            raise KeyError(f"Fact '{fid}' already indexed")
        eids = version.evidence_ids
        self._add(fid, (fact, version), fact.subject, fact.predicate, eids)

    def update_current(self, fact_id: str, version: FactVersion) -> None:
        """Actualiza la versión vigente de un Fact ya indexado."""
        self._check_mutable()
        entry = self._by_id.get(fact_id)
        if entry is None:
            raise KeyError(f"Fact '{fact_id}' not found")
        if isinstance(entry, tuple):
            fact = entry[0]
            self._by_id[fact_id] = (fact, version)

    # ── Lookup ────────────────────────────────────────

    def lookup(self, fact_id: str) -> Any | None:
        return self._by_id.get(fact_id)

    def lookup_entity(self, entity: str) -> list[Any]:
        return self._resolve_ids(self._by_entity.get(entity.lower()))

    def lookup_predicate(self, predicate: str) -> list[Any]:
        return self._resolve_ids(self._by_predicate.get(predicate.lower()))

    def lookup_subject_predicate(self, subject: str, predicate: str) -> list[Any]:
        return self._resolve_ids(
            self._by_sp.get((subject.lower(), predicate.lower()))
        )

    def lookup_evidence(self, evidence_id: str) -> list[Any]:
        return self._resolve_ids(self._by_evidence.get(evidence_id))

    # ── Estado ────────────────────────────────────────

    @property
    def size(self) -> int:
        return len(self._by_id)

    @property
    def frozen(self) -> bool:
        return self._frozen

    def freeze(self) -> None:
        self._frozen = True

    # ── Construcción por lotes ─────────────────────────

    @classmethod
    def build(cls, facts: list[KnowledgeFact]) -> FactIndex:
        idx = cls()
        for fact in facts:
            if not fact.id or fact.id in idx._by_id:
                continue
            idx.add_fact(fact)
        idx.freeze()
        return idx

    @classmethod
    def build_from_versions(
        cls, entries: list[tuple[Fact, FactVersion]],
    ) -> FactIndex:
        idx = cls()
        for fact, version in entries:
            if fact.fact_id in idx._by_id:
                continue
            idx.add_fact_version(fact, version)
        idx.freeze()
        return idx

    def copy(self) -> FactIndex:
        new = FactIndex()
        new._by_id = dict(self._by_id)
        new._by_entity = {k: dict(v) for k, v in self._by_entity.items()}
        new._by_predicate = {k: dict(v) for k, v in self._by_predicate.items()}
        new._by_sp = {k: dict(v) for k, v in self._by_sp.items()}
        new._by_evidence = {k: dict(v) for k, v in self._by_evidence.items()}
        return new

    # ── Internos ───────────────────────────────────────

    def _check_mutable(self) -> None:
        if self._frozen:
            raise RuntimeError("Cannot modify frozen FactIndex")

    def _add(self, fid: str, obj: Any, subj: str, pred: str, eids: tuple[str, ...]) -> None:
        if not fid:
            raise ValueError("Fact must have a non-empty id")
        if fid in self._by_id:
            raise KeyError(f"Fact '{fid}' already indexed")
        self._by_id[fid] = obj
        self._add_to_ordered_set(self._by_entity, subj.lower(), fid)
        self._add_to_ordered_set(self._by_predicate, pred.lower(), fid)
        self._add_to_ordered_set(self._by_sp, (subj.lower(), pred.lower()), fid)
        for eid in eids:
            if eid:
                self._add_to_ordered_set(self._by_evidence, eid, fid)

    @staticmethod
    def _extract_keys(entry: Any) -> tuple[str, str, tuple[str, ...]]:
        if isinstance(entry, tuple):
            fact, version = entry
            return fact.subject, fact.predicate, version.evidence_ids
        return entry.subject, entry.predicate, entry.evidence_ids

    @staticmethod
    def _add_to_ordered_set(index: dict, key: object, fact_id: str) -> None:
        inner = index.get(key)
        if inner is None:
            inner = {}
            index[key] = inner
        inner[fact_id] = None

    @staticmethod
    def _remove_from_ordered_set(index: dict, key: object, fact_id: str) -> None:
        inner = index.get(key)
        if inner is not None:
            inner.pop(fact_id, None)

    def _resolve_ids(self, ordered_set: dict[str, None] | None) -> list[Any]:
        if ordered_set is None:
            return []
        return [self._by_id[fid] for fid in ordered_set if fid in self._by_id]
