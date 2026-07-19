"""Feedback — sistema de retroalimentación y overlay de ranking.

Almacena valoraciones de documentos en op_feedback_agg.
Aplica overlay de ranking en búsquedas (docs mejor valorados suben en resultados).

Principios:
  - Nunca modifica kg_*. Solo op_feedback_agg.
  - El overlay de ranking es determinista (mismos ratings → mismo orden).
  - Feedback es best-effort: nunca bloquea búsquedas.
  - doc_id validado: 12 caracteres hexadecimales (formato SHA-256[:12]).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.feedback")

_RATING_MIN = 1
_RATING_MAX = 5
_RATING_BOOST_FACTOR = 0.2
_DOC_ID_PATTERN = "0123456789abcdef"


class InvalidDocIdError(ValueError):
    """doc_id no tiene el formato esperado (12 hex chars)."""


def _validate_doc_id(doc_id: str) -> None:
    """Valida que doc_id sea un hash SHA-256[:12]."""
    if not doc_id or len(doc_id) != 12:
        raise InvalidDocIdError(f"doc_id must be 12 hex chars, got {len(doc_id)}")
    if not all(c in _DOC_ID_PATTERN for c in doc_id):
        raise InvalidDocIdError("doc_id must be hexadecimal (0-9 a-f)")


@dataclass(frozen=True)
class Feedback:
    """Una valoración de documento."""

    doc_id: str
    rating: int
    timestamp: str = ""


def record_feedback(db_path: Path, doc_id: str, rating: int) -> bool:
    """Registra una valoración en op_feedback_agg.

    Atómico: BEGIN IMMEDIATE → SELECT → INSERT OR REPLACE → COMMIT.
    Si falla, la transacción se revierte automáticamente al cerrar la conexión.

    Args:
        db_path: Ruta a la base de datos.
        doc_id: ID del documento (12 hex chars).
        rating: Puntuación (1-5).

    Returns:
        True si se registró correctamente.
    """
    if rating < _RATING_MIN or rating > _RATING_MAX:
        log.warning("Rating fuera de rango: %d", rating)
        return False
    try:
        _validate_doc_id(doc_id)
    except InvalidDocIdError as exc:
        log.warning("doc_id inválido: %s — %s", doc_id, exc)
        return False

    from knowledge.engine.connection import begin_immediate, open_db

    try:
        conn = open_db(db_path)
        begin_immediate(conn)

        row = conn.execute(
            "SELECT n_ratings, avg_rating FROM op_feedback_agg WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()

        if row:
            n = row["n_ratings"] + 1
            avg = ((row["avg_rating"] * row["n_ratings"]) + rating) / n
        else:
            n = 1
            avg = float(rating)

        now = datetime.now(UTC).isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO op_feedback_agg "
            "(doc_id, n_ratings, avg_rating, last_feedback_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?)",
            (doc_id, n, avg, now, now),
        )
        conn.commit()
        conn.close()
        log.debug("Feedback recorded: doc=%s rating=%d (avg=%.2f, n=%d)", doc_id, rating, avg, n)
        return True
    except Exception as exc:
        log.warning("Error recording feedback: %s", exc)
        return False


def get_feedback(db_path: Path, doc_id: str) -> Feedback | None:
    """Obtiene la valoración de un documento."""
    from knowledge.engine.connection import open_db

    try:
        _validate_doc_id(doc_id)
    except InvalidDocIdError:
        return None

    try:
        conn = open_db(db_path)
        row = conn.execute(
            "SELECT n_ratings, avg_rating, last_feedback_at FROM op_feedback_agg WHERE doc_id = ?",
            (doc_id,),
        ).fetchone()
        conn.close()
        if row:
            return Feedback(
                doc_id=doc_id,
                rating=round(row["avg_rating"]),
                timestamp=row["last_feedback_at"] or "",
            )
        return None
    except Exception:
        return None


def apply_ranking_overlay(
    results: list[dict[str, Any]],
    db_path: Path,
) -> list[dict[str, Any]]:
    """Aplica overlay de ranking: docs mejor valorados suben en resultados.

    No modifica la base de datos. Solo lectura de op_feedback_agg.
    Una sola query SQL (no N+1). Resultados ordenados por score descendente.

    Args:
        results: Resultados de búsqueda como dicts con 'doc_id' y 'score'.
        db_path: Ruta a la base de datos.

    Returns:
        Nueva lista con overlay aplicado (no muta la original).
    """
    if not results:
        return list(results)

    from knowledge.engine.connection import open_db

    try:
        conn = open_db(db_path)
        doc_ids = [r["doc_id"] for r in results]
        placeholders = ",".join("?" * len(doc_ids))
        rows = conn.execute(
            f"SELECT doc_id, avg_rating, n_ratings FROM op_feedback_agg WHERE doc_id IN ({placeholders})",
            doc_ids,
        ).fetchall()
        conn.close()

        fb_map: dict[str, dict[str, Any]] = {r["doc_id"]: dict(r) for r in rows}

        new_results: list[dict[str, Any]] = []
        for r in results:
            entry = dict(r)  # copia para no mutar original
            fb = fb_map.get(entry["doc_id"])
            avg = fb["avg_rating"] if fb else 3.0
            boost = (avg - 3.0) * _RATING_BOOST_FACTOR
            entry["score"] = entry.get("score", 0.0) + boost
            entry["avg_rating"] = round(avg, 2)
            entry["n_ratings"] = fb["n_ratings"] if fb else 0
            new_results.append(entry)

        new_results.sort(key=lambda r: r["score"], reverse=True)
        return new_results
    except Exception as exc:
        log.debug("Ranking overlay error: %s", exc)
        return list(results)


def top_rated(db_path: Path, limit: int = 10) -> list[Feedback]:
    """Retorna los documentos mejor valorados.

    Realiza un full scan de op_feedback_agg. Para conjuntos grandes,
    considere añadir un índice: CREATE INDEX idx_feedback_rating ON op_feedback_agg(avg_rating DESC, n_ratings DESC).
    """
    from knowledge.engine.connection import open_db

    try:
        conn = open_db(db_path)
        rows = conn.execute(
            "SELECT doc_id, avg_rating, last_feedback_at FROM op_feedback_agg "
            "ORDER BY avg_rating DESC, n_ratings DESC LIMIT ?",
            (limit,),
        ).fetchall()
        conn.close()
        return [
            Feedback(doc_id=r["doc_id"], rating=round(r["avg_rating"]), timestamp=r["last_feedback_at"] or "")
            for r in rows
        ]
    except Exception:
        return []
