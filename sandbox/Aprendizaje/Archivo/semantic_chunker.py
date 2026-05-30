#!/usr/bin/env python3
"""Fragmentador semántico para la Biblioteca de URA usando Chonkie."""

import json
import os
from pathlib import Path
from chonkie import SemanticChunker

ARCHIVO_DIR = Path(
    os.environ.get("ARCHIVO_DIR", Path.home() / "URA/ura_ia_1972/sandbox/Aprendizaje/Archivo")
)
chunker = SemanticChunker(threshold=0.7)

for doc_path in sorted(ARCHIVO_DIR.glob("documentos/**/*.txt")):
    if doc_path.stat().st_size == 0:
        continue
    text = doc_path.read_text()
    chunks = chunker.chunk(text)
    output_path = ARCHIVO_DIR / "fragmentos" / f"{doc_path.stem}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(
            {
                "source": str(doc_path),
                "chunks": [
                    {
                        "id": f"{doc_path.stem}_{i}",
                        "text": c,
                        "effectiveness": "settled",
                        "quarantine": False,
                        "reinforced": False,
                    }
                    for i, c in enumerate(chunks)
                ],
            },
            f,
            ensure_ascii=False,
            indent=2,
        )
    print(f"✅ {doc_path.name}: {len(chunks)} fragmentos")
