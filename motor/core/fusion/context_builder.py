"""ContextBuilder — construye contexto para LLM desde FactIndex (F25-A3).

Flujo: FactIndex → Query → Facts (solo vigentes) → Formatted Context → Prompt

Reglas:
- Solo incluye Facts de la versión vigente (no obsoletos, no tombstones)
- Nunca consulta SemanticFact ni FactHistory directamente
- Una única fuente de lectura: FactIndex
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from motor.core.fusion.fact_index import FactIndex

_DEFAULT_MAX_FACTS = 50


class ContextBuilder:
    """Construye contexto textual para LLM desde Facts indexados.

    Uso tipico:
        result = pipeline.run(bundle, doc)
        builder = ContextBuilder(result.index)
        prompt_context = builder.build_context(query="que vende apple?")
    """

    def __init__(self, index: FactIndex | None = None) -> None:
        self._index = index

    @property
    def index(self) -> FactIndex | None:
        return self._index

    def set_index(self, index: FactIndex) -> None:
        self._index = index

    def build_context(
        self,
        query: str = "",
        max_facts: int = _DEFAULT_MAX_FACTS,
        include_entities: list[str] | None = None,
    ) -> str:
        """Construye un bloque de contexto a partir del FactIndex."""
        if self._index is None:
            return ""

        entries = self._collect_facts(query, include_entities)
        formatted = [self._format_fact(e) for e in entries[:max_facts]]

        if not formatted:
            return ""

        lines = ["# Conocimiento disponible", ""]
        lines.extend(formatted)
        return "\n".join(lines)

    # ── helpers ──────────────────────────────────────

    def _collect_facts(self, query: str, include_entities: list[str] | None) -> list:
        """Recolecta facts vigentes desde el índice por entidad o consulta.

        Solo incluye Facts de la versión vigente. Versiones obsoletas
        (SUPERSEDED, ROLLED_BACK, TOMBSTONE) se excluyen automáticamente.
        """
        idx = self._index
        if idx is None:
            return []

        from motor.core.fusion.models import VersionState

        seen: set[str] = set()
        result: list = []

        entities = include_entities or []

        if not entities and query:
            words = [w.lower() for w in query.split() if len(w) > 2]
            entities = words[:10]

        for entity in entities:
            matches = idx.lookup_entity(entity)
            for entry in matches:
                if not self._is_current_version(entry, VersionState):
                    continue
                fid = self._entry_id(entry)
                if fid not in seen:
                    seen.add(fid)
                    result.append(entry)

        return result

    @staticmethod
    def _is_current_version(entry: Any, vs: type) -> bool:
        """Verifica que el entry sea de la versión vigente.

        Para (Fact, FactVersion): solo CURRENT.
        Para KnowledgeFact (legacy): siempre se considera vigente.
        """
        if isinstance(entry, tuple):
            _, version = entry
            return getattr(version, "state", None) == vs.CURRENT
        return True

    @staticmethod
    def _entry_id(entry) -> str:
        if isinstance(entry, tuple):
            return entry[0].fact_id
        return entry.id

    @staticmethod
    def _format_fact(entry) -> str:
        if isinstance(entry, tuple):
            fact, version = entry
            return f"- {fact.subject} | {fact.predicate} | {fact.object} (confianza: {version.confidence:.2f})"
        return f"- {entry.subject} | {entry.predicate} | {entry.object} (confianza: {entry.confidence:.2f})"
