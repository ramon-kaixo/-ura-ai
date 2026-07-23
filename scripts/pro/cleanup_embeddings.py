#!/usr/bin/env python3
"""Elimina embeddings sin documento asociado en knowledge/."""

from pathlib import Path

EMB_DIR = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "embeddings"
DOC_DIR = Path.home() / "URA" / "ura_ia_1972" / "knowledge" / "documents"


def cleanup():
    if not EMB_DIR.exists():
        print("Embeddings dir no existe")
        return 0
    removed = 0
    for emb in EMB_DIR.iterdir():
        doc = DOC_DIR / emb.name
        if not doc.exists():
            emb.unlink()
            removed += 1
    print(f"Eliminados {removed} embeddings huerfanos")
    return removed


if __name__ == "__main__":
    cleanup()
