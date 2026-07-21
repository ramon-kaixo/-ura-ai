"""Repository protocol — separa el dominio de la infraestructura.

El dominio (compiler, reader, rules) conoce interfaces (Protocol),
no implementaciones concretas (SQLite, Qdrant, NDJSON).

Uso:
    repo: KnowledgeRepository = SQLiteKnowledgeRepository(db_path)
    repo.save_nodes(nodes)
    doc = repo.get_document(doc_id)
"""

from __future__ import annotations

import json
import logging
from abc import abstractmethod
from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from pathlib import Path

    from knowledge.engine.models import Document, Relation, SearchResult

log = logging.getLogger("ura.knowledge.repository")


class KnowledgeRepository(Protocol):
    """Contrato para el repositorio de conocimiento.

    Cualquier implementación (SQLite, PostgreSQL, mock) debe cumplir
    este Protocol. El dominio nunca conoce SQLite directamente.
    """

    @abstractmethod
    def get_document(self, doc_id: str) -> Document | None:
        """Retorna un documento por su ID."""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        mode: str = "lexical",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        """Búsqueda full-text."""
        ...

    @abstractmethod
    def related(
        self,
        doc_id: str,
        relation: str | None = None,
        depth: int = 2,
    ) -> list[Relation]:
        """Documentos relacionados."""
        ...

    @abstractmethod
    def get_node_ids(self) -> set[str]:
        """Todos los IDs de nodos del grafo."""
        ...

    @abstractmethod
    def get_relation_targets(self) -> set[str]:
        """Todos los destinos de edges."""
        ...

    @abstractmethod
    def get_documents_for_rules(self) -> tuple[list[dict], set[str], set[str]]:
        """Datos para evaluación de reglas: docs, node_ids, targets."""
        ...

    @abstractmethod
    def health_check(self) -> dict[str, Any]:
        """Estado de salud del repositorio."""
        ...


class SQLiteKnowledgeRepository:
    """Implementación SQLite del repositorio de conocimiento.

    Toda la lógica SQLite está encapsulada aquí.
    Ningún otro módulo del dominio toca SQLite directamente.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def get_document(self, doc_id: str) -> Document | None:
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(db_path=self._db_path)
        return reader.get_document(doc_id)

    def search(
        self,
        query: str,
        mode: str = "lexical",
        filters: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> list[SearchResult]:
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(db_path=self._db_path)
        return reader.search(query, mode=mode, filters=filters, limit=limit)

    def related(
        self,
        doc_id: str,
        relation: str | None = None,
        depth: int = 2,
    ) -> list[Relation]:
        from knowledge.engine.reader import KnowledgeReader

        reader = KnowledgeReader(db_path=self._db_path)
        return reader.related(doc_id, relation_type=relation, depth=depth)

    def get_node_ids(self) -> set[str]:
        from knowledge.engine.connection import open_db

        conn = open_db(self._db_path)
        ids = {r["id"] for r in conn.execute("SELECT id FROM kg_nodes").fetchall()}
        conn.close()
        return ids

    def get_relation_targets(self) -> set[str]:
        from knowledge.engine.connection import open_db

        conn = open_db(self._db_path)
        targets = {e["dst"] for e in conn.execute("SELECT dst FROM kg_edges").fetchall()}
        conn.close()
        return targets

    def get_documents_for_rules(self) -> tuple[list[dict], set[str], set[str]]:
        from knowledge.engine.connection import open_db

        conn = open_db(self._db_path)
        rows = conn.execute("SELECT id, type, path, frontmatter, body FROM kg_nodes").fetchall()
        edges = conn.execute("SELECT src, dst FROM kg_edges").fetchall()
        conn.close()

        node_ids = {r["id"] for r in rows}
        targets = {e["dst"] for e in edges}
        docs = []
        for r in rows:
            fm = json.loads(r["frontmatter"]) if r["frontmatter"] else {}
            docs.append(
                {
                    "id": r["id"],
                    "path": r["path"],
                    "title": fm.get("title", ""),
                    "tags": fm.get("tags", []),
                    "body": r["body"] or "",
                    "relations": [e["dst"] for e in edges if e["src"] == r["id"]],
                },
            )
        return docs, node_ids, targets

    def health_check(self) -> dict[str, Any]:
        from knowledge.engine.connection import open_db

        try:
            conn = open_db(self._db_path)
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            version = conn.execute("PRAGMA user_version").fetchone()[0]
            conn.close()
            return {"healthy": integrity == "ok", "schema_version": version, "integrity": integrity}
        except Exception as exc:
            return {"healthy": False, "error": str(exc)}
