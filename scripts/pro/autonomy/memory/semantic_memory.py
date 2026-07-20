"""SemanticMemory — capa de conocimiento estructurado sobre el ExecutionLedger.

Consume el ledger (JSON) y lo transforma en SQLite con índices.
Permite consultas eficientes por objetivo, plugin, fecha y decisión.
Respeta ADR-030: no modifica infraestructura existente.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from scripts.pro.autonomy.memory.ingester import LedgerIngester
from scripts.pro.autonomy.memory.queries import SemanticQueries


class SemanticMemory:
    """Memoria semántica: ledger → SQLite → consultas estructuradas."""

    def __init__(self, db_path: Path, nervioso: Path) -> None:
        self._db_path = db_path
        self._nervioso = nervioso
        self._ingester = LedgerIngester(db_path, nervioso)
        self._queries = SemanticQueries(db_path)

    @property
    def queries(self) -> SemanticQueries:
        return self._queries

    def sync(self, max_entries: int = 0) -> dict[str, Any]:
        """Sincroniza el ledger con SQLite. Retorna estadísticas de ingesta."""
        return self._ingester.ingest(max_entries=max_entries)

    def rebuild(self) -> dict[str, Any]:
        """Reconstruye la base desde cero (útil si cambia el schema)."""
        if self._db_path.exists():
            self._db_path.unlink()
        self._ingester = LedgerIngester(self._db_path, self._nervioso)
        self._queries = SemanticQueries(self._db_path)
        return self._ingester.ingest()

    def summary(self) -> dict[str, Any]:
        """Retorna resumen de la memoria semántica."""
        size = self._queries.total_size()
        rate = self._queries.promotion_rate()
        return {
            "basedatos": str(self._db_path),
            **size,
            "tasa_promocion": rate.get("rate", 0),
        }

    def close(self) -> None:
        self._queries.close()
