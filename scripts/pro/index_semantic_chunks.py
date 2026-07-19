#!/usr/bin/env python3
"""Index golden documents with SemanticChunker for KE 2.0 comparison.
Uses a separate Qdrant collection (ura_docs_semantic) to coexist with KE 1.x.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
logging.basicConfig(level=logging.INFO, format="%(name)s %(levelname)s %(message)s")
log = logging.getLogger("index_semantic")

KE2_COLLECTION = "ura_docs_semantic"
DOCS_DIR = Path(__file__).resolve().parent.parent.parent / "knowledge" / "evaluation" / "golden_docs"


def main() -> int:  # noqa: C901
    from motor.core.config import UraConfig
    from motor.core.qdrant_client import QdrantClient
    from motor.intelligence.chunking import SemanticChunker

    cfg = UraConfig()
    qc = QdrantClient.instancia(cfg)
    if not qc.disponible:
        log.error("Qdrant not available")
        return 1

    # Create collection if not exists
    try:
        from qdrant_client.http import models

        if qc._cliente:  # noqa: SLF001
            collections = [c.name for c in qc._cliente.get_collections().collections]  # noqa: SLF001
            if KE2_COLLECTION not in collections:
                qc._cliente.create_collection(  # noqa: SLF001
                    collection_name=KE2_COLLECTION,
                    vectors_config=models.VectorParams(size=768, distance=models.Distance.COSINE),
                )
                log.info("Created collection: %s", KE2_COLLECTION)
    except Exception as e:
        log.warning("Could not create collection (may exist): %s", e)

    chunker = SemanticChunker(max_tokens=512, overlap_tokens=64)
    total_chunks = 0

    for md_file in sorted(DOCS_DIR.glob("*.md")):
        doc_id = md_file.stem
        content = md_file.read_text().strip()
        chunks = chunker.chunk(content, doc_id=doc_id)

        for chunk in chunks:
            texto = chunk.texto
            metadata = {
                "id": chunk.chunk_id,
                "texto": texto,
                "source": doc_id,
                "title": doc_id.replace("_", " ").title(),
                "section": chunk.section,
                "chunk_index": chunk.chunk_index,
                "doc_type": "evaluation",
                "chunk_version": "semantic_v1",
            }

            # Generate embedding and upsert
            vector = qc.generar_embedding(texto)
            if qc._cliente:  # noqa: SLF001
                from qdrant_client.http import models

                point_id = hash(chunk.chunk_id) % (10**12)
                qc._cliente.upsert(  # noqa: SLF001
                    collection_name=KE2_COLLECTION,
                    points=[models.PointStruct(id=point_id, vector=vector, payload=metadata)],
                )
            total_chunks += 1
            log.debug("Indexed %s chunk %d", doc_id, chunk.chunk_index)

    log.info("Indexed %d semantic chunks into %s", total_chunks, KE2_COLLECTION)

    # Validate
    log.info("Validating KE 2.0 index...")
    found = 0
    for md_file in sorted(DOCS_DIR.glob("*.md")):
        doc_id = md_file.stem
        vector = qc.generar_embedding(doc_id.replace("_", " "))
        if qc._cliente:  # noqa: SLF001
            hits = qc._cliente.search(  # noqa: SLF001
                collection_name=KE2_COLLECTION,
                query_vector=vector,
                limit=1,
            )
            if hits:
                found += 1
                log.info("  %s: FOUND (score=%.4f)", doc_id, hits[0].score)
            else:
                log.warning("  %s: NOT FOUND", doc_id)

    log.info(
        "KE 2.0 coverage: %d/%d = %.1f%%",
        found,
        len(list(DOCS_DIR.glob("*.md"))),
        found / len(list(DOCS_DIR.glob("*.md"))) * 100,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
