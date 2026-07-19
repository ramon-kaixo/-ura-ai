#!/usr/bin/env python3
"""reindex_vectors.py — Reindexa todos los assets en el VectorStore.

Uso:
    python3 scripts/pro/reindex_vectors.py [--db PATH] [--execute] [--batch N]

Por defecto: dry-run (solo reporta qué se necesita reindexar).
Con --execute: realmente embeddea y upsert.
"""

from __future__ import annotations

import argparse
import logging
from pathlib import Path

from knowledge.engine.asset_store import SQLiteAssetStore
from knowledge.engine.graphrag import SQLiteGraphRetriever
from knowledge.engine.vector_ollama import OllamaEmbedder
from knowledge.engine.vector_qdrant import QdrantVectorStore
from knowledge.engine.vector_retriever import VectorAugmentedRetriever

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger("reindex_vectors")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reindexa assets en VectorStore")
    parser.add_argument(
        "--db",
        default="/home/ramon/URA/ura_ia_1972/data/ura.db",
        type=Path,
        help="Ruta a la BD SQLite",
    )
    parser.add_argument("--execute", action="store_true", help="Ejecutar realmente (dry-run por defecto)")
    parser.add_argument("--batch", type=int, default=100, help="Tamaño de batch")
    args = parser.parse_args()

    db_path = args.db.resolve()
    if not db_path.exists():
        log.error("Database not found: %s", db_path)
        return

    embedder = OllamaEmbedder()
    vector_store = QdrantVectorStore()
    graph = SQLiteGraphRetriever(db_path)
    asset_store = SQLiteAssetStore(db_path)
    retriever = VectorAugmentedRetriever(graph, asset_store, embedder, vector_store)

    log.info("Reconciliando AssetStore ↔ VectorStore (dry_run=%s, batch=%d)", not args.execute, args.batch)
    stats = retriever.reconcile(dry_run=not args.execute, batch_size=args.batch)

    log.info("Resultados:")
    log.info("  To upsert: %d", stats["to_upsert"])
    log.info("  To delete: %d", stats["to_delete"])
    log.info("  Upserted:  %d", stats["upserted"])
    log.info("  Deleted:   %d", stats["deleted"])

    if stats["to_upsert"] > 0 and not args.execute:
        log.info("Usa --execute para aplicar los cambios.")


if __name__ == "__main__":
    main()
