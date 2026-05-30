#!/usr/bin/env python3
"""vectorizar_docs.py — Indexacion vectorial con embeddings reales de Ollama."""

import chromadb
import hashlib
import json
import os
from pathlib import Path
import urllib.request
from urllib.parse import urlparse

CHROMA_DIR = "/opt/ura/chroma_docs"
DOCS_DIR = Path(os.path.expanduser("~/URA/ura_ia_1972/docs"))
COLLECTION = "ura_docs"
OLLAMA_URL = "http://10.164.1.99:11434/api/embeddings"
MODEL = "nomic-embed-text"

ALLOWED_HOSTS = {"10.164.1.99", "127.0.0.1", "localhost"}


def _validar_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname or ""
    return host in ALLOWED_HOSTS


def get_embedding(text):
    if not _validar_url(OLLAMA_URL):
        print(f"  Error: URL no permitida: {OLLAMA_URL}")
        return None
    try:
        payload = json.dumps({"model": MODEL, "prompt": text[:500]}).encode()
        req = urllib.request.Request(
            OLLAMA_URL, data=payload, headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=30) as r:  # nosec B310
            return json.loads(r.read())["embedding"]
    except Exception as e:
        print(f"  Error: {e}")
        return None


def main():
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    collection = chroma_client.get_or_create_collection(COLLECTION)

    archivos = list(DOCS_DIR.rglob("*.md"))
    print(f"Indexando {len(archivos)} documentos con {MODEL}...")

    for md_file in archivos:
        with open(md_file) as f:
            content = f.read()
        if not content.strip():
            continue
        doc_id = hashlib.md5(str(md_file).encode(), usedforsecurity=False).hexdigest()
        embedding = get_embedding(content[:500])
        if embedding:
            collection.upsert(
                documents=[content[:2000]],
                embeddings=[embedding],
                metadatas=[{"fuente": str(md_file.relative_to(DOCS_DIR))}],
                ids=[doc_id],
            )
            print(f"  ✅ {md_file.name}")

    print(f"\nTotal: {collection.count()} documentos indexados en ChromaDB")


if __name__ == "__main__":
    main()
