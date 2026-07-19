"""Determinism hash — verificación de reproducibilidad del grafo compilado.

El hash cubre el contenido semántico de kg_nodes y kg_edges,
EXCLUYENDO updated_at, swapped_at y otros metadatos temporales.
Dos compiles del mismo commit deben producir el mismo hash.

Algoritmo (sha256-v2):
  HASH = SHA-256(
    json.dumps(
      {
        "nodes": [dict(id, type, path, content_sha256, body, frontmatter,
                       quality, confidence, embed_hash)
                  for row in kg_nodes ORDER BY id],
        "edges": [dict(src, dst, relation)
                  for row in kg_edges ORDER BY src, dst, relation]
      },
      sort_keys=True
    ).encode()
  )

El algoritmo está versionado (determinism_algorithm = "sha256-v1")
para permitir cambios futuros sin romper el histórico.
"""

from __future__ import annotations

import hashlib
import json
import logging
from typing import TYPE_CHECKING

from knowledge.engine.connection import open_db

if TYPE_CHECKING:
    from pathlib import Path

log = logging.getLogger("ura.knowledge.determinism")

_ALGORITHM_VERSION = "sha256-v2"


def record_determinism_hash(db_path: Path, run_id: int) -> None:
    """Calcula y persiste el hash de determinismo más la versión del algoritmo."""
    try:
        conn = open_db(db_path)
        rows = conn.execute(
            "SELECT id, type, path, content_sha256, body, frontmatter, "
            "       quality, confidence "
            "FROM kg_nodes ORDER BY id"
        ).fetchall()
        node_data = [dict(r) for r in rows]

        edges = conn.execute("SELECT src, dst, relation FROM kg_edges ORDER BY src, dst, relation").fetchall()
        edge_data = [dict(e) for e in edges]

        canonical = json.dumps(
            {"nodes": node_data, "edges": edge_data},
            sort_keys=True,
            # Sin separators/ensure_ascii explícitos.
            # v2: excluye embed_hash (columna siempre NULL).
        )
        content_hash = hashlib.sha256(canonical.encode()).hexdigest()

        conn.execute(
            "UPDATE kg_active_version SET determinism_hash = ?, determinism_algorithm = ? WHERE singleton = 1",
            (content_hash, _ALGORITHM_VERSION),
        )
        conn.commit()
        conn.close()

        log.info(
            "Determinism hash: %s algo=%s (run_id=%d)",
            content_hash[:16],
            _ALGORITHM_VERSION,
            run_id,
        )
    except Exception as exc:
        log.warning("No se pudo registrar determinism hash: %s", exc)


def get_determinism_hash(db_path: Path) -> str | None:
    """Retorna el determinism_hash del último compile."""
    try:
        conn = open_db(db_path)
        row = conn.execute("SELECT determinism_hash FROM kg_active_version WHERE singleton = 1").fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def get_determinism_algorithm(db_path: Path) -> str:
    """Retorna la versión del algoritmo usado para el último hash.

    Si la DB no tiene la columna (pre-v10), retorna "sha256-v1".
    Si tiene la columna pero vacía (v10-v11), retorna "sha256-v1".
    A partir de v12+, el algoritmo puede ser "sha256-v2".
    """
    try:
        conn = open_db(db_path)
        row = conn.execute("SELECT determinism_algorithm FROM kg_active_version WHERE singleton = 1").fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
        return "sha256-v1"  # pre-v12 o vacío
    except Exception:
        # Columna no existe (pre-v10) o error → asumir v1
        return "sha256-v1"
