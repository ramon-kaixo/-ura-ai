"""FactIndex — índice de hechos (R06, F25-B4).

Componente arquitectónico independiente para indexación y consulta
eficiente de KnowledgeFact.

No depende de FusionPipeline, KnowledgeMerger ni EntityResolver.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from motor.core.fusion.models import KnowledgeFact


class FactIndex:
    """Índice de hechos con índices secundarios.

    Responsabilidad única: indexar hechos y localizarlos eficientemente.

    Índices mantenidos (todos O(1) amortizado):
    - fact_id → KnowledgeFact (índice primario)
    - entity (subject) → ordered set[fact_id]
    - predicate → ordered set[fact_id]
    - (subject, predicate) → ordered set[fact_id]
    - evidence_id → ordered set[fact_id]

    Los índices secundarios usan dict como ordered set (O(1) add/remove,
    preserva orden de inserción). No hay duplicados.

    Complejidad garantizada:
    - add_fact: O(k) donde k = número de índices secundarios = 5 (constante)
    - remove_fact: O(k · m) donde m = evidence_ids (constante práctico)
    - lookup primario: O(1)
    - lookup secundario: O(1) para obtener set, O(m) para resolver facts

    Contrato de concurrencia:
    - Lecturas concurrentes: seguras (dict.get es atómico en CPython).
    - Escrituras: deben serializarse externamente.
    - Reemplazo atómico: build() → freeze() → swap referencia.
    - Una vez frozen, el índice es inmutable y thread-safe.

    Inmutabilidad:
    - KnowledgeFact nunca se modifica. El índice solo almacena referencias.
    - Los índices secundarios son dicts internos; no se exponen directamente.

    copy() y structural sharing:
    - Los KnowledgeFact referenciados se comparten (no se copian).
    - Los dicts de índices son copias shallow (nuevos objetos dict).
    - Los ordered sets internos (dict[str, None]) también se copian.
    - El nuevo índice NO está frozen.
    """

    def __init__(self) -> None:
        self._by_id: dict[str, KnowledgeFact] = {}
        self._by_entity: dict[str, dict[str, None]] = {}
        self._by_predicate: dict[str, dict[str, None]] = {}
        self._by_sp: dict[tuple[str, str], dict[str, None]] = {}
        self._by_evidence: dict[str, dict[str, None]] = {}
        self._frozen: bool = False

    # ── API pública ──────────────────────────────────

    def add_fact(self, fact: KnowledgeFact) -> None:
        """Indexa un KnowledgeFact en todos los índices secundarios.

        O(k) donde k = número de índices.
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
        self._add_to_ordered_set(self._by_entity, fact.subject.lower(), fid)
        self._add_to_ordered_set(self._by_predicate, fact.predicate.lower(), fid)
        sp_key = (fact.subject.lower(), fact.predicate.lower())
        self._add_to_ordered_set(self._by_sp, sp_key, fid)
        for eid in fact.evidence_ids:
            if eid:
                self._add_to_ordered_set(self._by_evidence, eid, fid)

    def remove_fact(self, fact_id: str) -> KnowledgeFact:
        """Elimina un fact del índice y retorna el KnowledgeFact.

        O(k · m) donde k = índices, m = evidence_ids.
        Lanza KeyError si fact_id no existe.
        Lanza RuntimeError si el índice está frozen.
        """
        if self._frozen:
            raise RuntimeError("Cannot modify frozen FactIndex")
        fact = self._by_id.pop(fact_id, None)
        if fact is None:
            raise KeyError(f"Fact '{fact_id}' not found")

        self._remove_from_ordered_set(self._by_entity, fact.subject.lower(), fact_id)
        self._remove_from_ordered_set(self._by_predicate, fact.predicate.lower(), fact_id)
        sp_key = (fact.subject.lower(), fact.predicate.lower())
        self._remove_from_ordered_set(self._by_sp, sp_key, fact_id)
        for eid in fact.evidence_ids:
            if eid:
                self._remove_from_ordered_set(self._by_evidence, eid, fact_id)
        return fact

    def lookup(self, fact_id: str) -> KnowledgeFact | None:
        """Retorna un KnowledgeFact por su fact_id. O(1)."""
        return self._by_id.get(fact_id)

    def lookup_entity(self, entity: str) -> list[KnowledgeFact]:
        """Retorna facts para una entidad (subject). O(1) + O(m)."""
        return self._resolve_ids(self._by_entity.get(entity.lower()))

    def lookup_predicate(self, predicate: str) -> list[KnowledgeFact]:
        """Retorna facts con un predicado. O(1) + O(m)."""
        return self._resolve_ids(self._by_predicate.get(predicate.lower()))

    def lookup_subject_predicate(self, subject: str, predicate: str) -> list[KnowledgeFact]:
        """Retorna facts con (subject, predicate). O(1) + O(m)."""
        return self._resolve_ids(
            self._by_sp.get((subject.lower(), predicate.lower()))
        )

    def lookup_evidence(self, evidence_id: str) -> list[KnowledgeFact]:
        """Retorna facts asociados a un evidence_id. O(1) + O(m)."""
        return self._resolve_ids(self._by_evidence.get(evidence_id))

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
        """Congela el índice para uso read-only y swapping atómico."""
        self._frozen = True

    # ── Construcción por lotes ─────────────────────────

    @classmethod
    def build(cls, facts: list[KnowledgeFact]) -> FactIndex:
        """Construye un FactIndex frozen desde una lista de facts.

        O(n). Si hay fact_ids duplicados, el primero prevalece.
        El índice resultante está frozen (inmutable, thread-safe).
        Equivale a: crear índice vacío + add_fact() secuencial + freeze().
        """
        idx = cls()
        for fact in facts:
            if not fact.id or fact.id in idx._by_id:
                continue
            idx.add_fact(fact)
        idx.freeze()
        return idx

    def copy(self) -> FactIndex:
        """Copia shallow para copy-on-write.

        - KnowledgeFact referenciados: compartidos (no se copian).
        - Dicts de índices: copias shallow (nuevos objetos).
        - Ordered sets internos (dict[str, None]): copias shallow.
        - El nuevo índice NO está frozen (permite escritura).
        """
        new = FactIndex()
        new._by_id = dict(self._by_id)
        new._by_entity = {k: dict(v) for k, v in self._by_entity.items()}
        new._by_predicate = {k: dict(v) for k, v in self._by_predicate.items()}
        new._by_sp = {k: dict(v) for k, v in self._by_sp.items()}
        new._by_evidence = {k: dict(v) for k, v in self._by_evidence.items()}
        return new

    # ── Helpers internos ────────────────────────────

    @staticmethod
    def _add_to_ordered_set(index: dict, key: object, fact_id: str) -> None:
        """Añade fact_id al ordered set (dict) para la clave dada. O(1)."""
        inner = index.get(key)
        if inner is None:
            inner = {}
            index[key] = inner
        inner[fact_id] = None

    @staticmethod
    def _remove_from_ordered_set(index: dict, key: object, fact_id: str) -> None:
        """Elimina fact_id del ordered set. O(1)."""
        inner = index.get(key)
        if inner is not None:
            inner.pop(fact_id, None)

    def _resolve_ids(self, ordered_set: dict[str, None] | None) -> list[KnowledgeFact]:
        """Convierte ordered set de fact_ids en lista de KnowledgeFact."""
        if ordered_set is None:
            return []
        return [self._by_id[fid] for fid in ordered_set if fid in self._by_id]
