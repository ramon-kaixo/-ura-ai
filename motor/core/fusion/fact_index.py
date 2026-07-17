"""FactIndex — índice de hechos (R06, F25-B4).

Componente arquitectónico independiente para indexación y consulta
eficiente de KnowledgeFact.

No depende de FusionPipeline, KnowledgeMerger ni EntityResolver.
"""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.models import KnowledgeFact


class FactIndex:
    """Índice de hechos con índices secundarios.

    Responsabilidad única: indexar hechos y localizarlos eficientemente.

    Índices mantenidos:
    - fact_id → KnowledgeFact (índice primario)
    - entity (subject) → list[fact_id]
    - predicate → list[fact_id]
    - (subject, predicate) → list[fact_id]
    - evidence_id → list[fact_id]

    Complejidad garantizada:
    - add_fact: O(1) amortizado por índice (k=5 índices, constante)
    - remove_fact: O(k · m) donde k=índices, m=evidence_ids (constante práctico)
    - lookup por clave primaria: O(1)
    - lookup por índice secundario: O(1) para obtener lista, O(m) para resolver facts

    Contrato de concurrencia:
    - Lecturas concurrentes: seguras (dict.get es atómico en CPython)
    - Escrituras: deben serializarse externamente
    - Reemplazo atómico: build() → freeze() → swap referencia
    - Una vez frozen, el índice es inmutable y puede compartirse entre threads

    Inmutabilidad:
    - KnowledgeFact nunca se modifica. El índice solo almacena referencias.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, KnowledgeFact] = {}
        self._by_entity: dict[str, list[str]] = {}
        self._by_predicate: dict[str, list[str]] = {}
        self._by_sp: dict[tuple[str, str], list[str]] = {}
        self._by_evidence: dict[str, list[str]] = {}
        self._frozen: bool = False

    # ── API pública ──────────────────────────────────

    def add_fact(self, fact: KnowledgeFact) -> None:
        """Indexa un KnowledgeFact en todos los índices secundarios.

        O(1) amortizado por índice.
        Lanza KeyError si el fact_id ya existe.
        Lanza RuntimeError si el índice está frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot modify frozen FactIndex")
        fid = fact.id
        if not fid:
            raise ValueError("Fact must have a non-empty id")
        if fid in self._by_id:
            raise KeyError(f"Fact '{fid}' already indexed")

        self._by_id[fid] = fact
        self._add_to_index(self._by_entity, fact.subject.lower(), fid)
        self._add_to_index(self._by_predicate, fact.predicate.lower(), fid)
        sp_key = (fact.subject.lower(), fact.predicate.lower())
        self._add_to_index(self._by_sp, sp_key, fid)
        for eid in fact.evidence_ids:
            if eid:
                self._add_to_index(self._by_evidence, eid, fid)

    def remove_fact(self, fact_id: str) -> KnowledgeFact:
        """Elimina un fact del índice y retorna el KnowledgeFact.

        O(k · m) donde k = número de índices, m = evidence_ids.
        Lanza KeyError si fact_id no existe.
        Lanza RuntimeError si el índice está frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot modify frozen FactIndex")
        fact = self._by_id.pop(fact_id, None)
        if fact is None:
            raise KeyError(f"Fact '{fact_id}' not found")

        self._remove_from_index(self._by_entity, fact.subject.lower(), fact_id)
        self._remove_from_index(self._by_predicate, fact.predicate.lower(), fact_id)
        sp_key = (fact.subject.lower(), fact.predicate.lower())
        self._remove_from_index(self._by_sp, sp_key, fact_id)
        for eid in fact.evidence_ids:
            if eid:
                self._remove_from_index(self._by_evidence, eid, fact_id)
        return fact

    def lookup(self, fact_id: str) -> KnowledgeFact | None:
        """Retorna un KnowledgeFact por su fact_id. O(1)."""
        return self._by_id.get(fact_id)

    def lookup_entity(self, entity: str) -> list[KnowledgeFact]:
        """Retorna todos los facts para una entidad (subject). O(1) + O(m)."""
        return self._resolve_ids(self._by_entity.get(entity.lower(), []))

    def lookup_predicate(self, predicate: str) -> list[KnowledgeFact]:
        """Retorna todos los facts con un predicado. O(1) + O(m)."""
        return self._resolve_ids(self._by_predicate.get(predicate.lower(), []))

    def lookup_subject_predicate(self, subject: str, predicate: str) -> list[KnowledgeFact]:
        """Retorna facts con (subject, predicate). O(1) + O(m)."""
        return self._resolve_ids(
            self._by_sp.get((subject.lower(), predicate.lower()), [])
        )

    def lookup_evidence(self, evidence_id: str) -> list[KnowledgeFact]:
        """Retorna facts asociados a un evidence_id. O(1) + O(m)."""
        return self._resolve_ids(self._by_evidence.get(evidence_id, []))

    # ── Propiedades de estado ─────────────────────────

    @property
    def size(self) -> int:
        """Número de facts indexados. O(1)."""
        return len(self._by_id)

    @property
    def frozen(self) -> bool:
        """True si el índice es inmutable."""
        return self._frozen

    def freeze(self) -> None:
        """Congela el índice para uso read-only y swapping atómico.

        Una vez frozen, add_fact y remove_fact lanzan RuntimeError.
        """
        self._frozen = True

    # ── Construcción por lotes ─────────────────────────

    @classmethod
    def build(cls, facts: list[KnowledgeFact]) -> FactIndex:
        """Construye un FactIndex frozen desde una lista de facts.

        O(n) donde n = número de facts.
        Si hay fact_ids duplicados, el primero prevalece (los siguientes se saltan).
        El índice resultante está frozen (inmutable, thread-safe).
        """
        idx = cls()
        for fact in facts:
            if not fact.id or fact.id in idx._by_id:
                continue
            idx.add_fact(fact)
        idx.freeze()
        return idx

    def copy(self) -> FactIndex:
        """Copia shallow del índice para copy-on-write.

        Los KnowledgeFact referenciados no se copian (compartidos).
        Las listas de fact_ids sí se copian (shallow copy).
        El nuevo índice NO está frozen.
        """
        new = FactIndex()
        new._by_id = dict(self._by_id)
        new._by_entity = {k: list(v) for k, v in self._by_entity.items()}
        new._by_predicate = {k: list(v) for k, v in self._by_predicate.items()}
        new._by_sp = {k: list(v) for k, v in self._by_sp.items()}
        new._by_evidence = {k: list(v) for k, v in self._by_evidence.items()}
        return new

    # ── Helpers internos ────────────────────────────

    @staticmethod
    def _add_to_index(index: dict, key: object, value: str) -> None:
        index.setdefault(key, []).append(value)

    @staticmethod
    def _remove_from_index(index: dict, key: object, value: str) -> None:
        lst = index.get(key)
        if lst is not None:
            with suppress(ValueError):
                lst.remove(value)

    def _resolve_ids(self, fact_ids: list[str]) -> list[KnowledgeFact]:
        return [self._by_id[fid] for fid in fact_ids if fid in self._by_id]
