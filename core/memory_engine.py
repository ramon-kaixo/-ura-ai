#!/usr/bin/env python3
"""Memory Engine — RAG (Retrieval-Augmented Generation) para URA.
Indexa documentos locales en ChromaDB y enriquece consultas con contexto.
Determinista: sin variables globales, todo el estado en disco.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import contextlib
import hashlib
import json
import logging
from datetime import datetime

from core.config_manager import CONFIG

log = logging.getLogger(__name__)

RAG_CONFIG = CONFIG.get("rag", {})
DATA_DIR = Path(CONFIG["paths"]["data"])
DOCS_DIR = DATA_DIR / "documentos"
CHROMA_DIR = DATA_DIR / "chroma_db"
MANIFEST_PATH = DATA_DIR / ".index_manifest.json"
CHUNK_SIZE = RAG_CONFIG.get("chunk_size", 500)
CHUNK_OVERLAP = RAG_CONFIG.get("chunk_overlap", 50)
TOP_K = RAG_CONFIG.get("top_k", 5)
SIMILARITY_THRESHOLD = RAG_CONFIG.get("threshold", 0.7)


def _sha256(filepath: Path) -> str:
    """Hash SHA-256 de un archivo (determinista)."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Divide texto en chunks con overlap (determinista)."""
    words = text.split()
    if len(words) <= size:
        return [text]
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + size, len(words))
        chunks.append(" ".join(words[start:end]))
        start += size - overlap
    return chunks


def _chromadb_available() -> bool:
    """Verifica si chromadb está instalado."""
    import importlib.util
    return importlib.util.find_spec("chromadb") is not None


def _get_collection():
    """Obtiene o crea la colección ChromaDB."""
    import chromadb
    CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return client.get_or_create_collection(
        name="ura_documents",
        metadata={"hnsw:space": "cosine"},
    )


# ============================================================
# Indexación (determinista: mismo input → mismo índice)
# ============================================================

def load_manifest() -> dict:
    """Carga el manifest de indexación."""
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except Exception as e:
            log.warning(f"Error cargando manifest: {e}")
    return {"indexed_at": None, "total_documents": 0, "total_chunks": 0, "files": {}}


def save_manifest(manifest: dict) -> None:
    """Guarda el manifest (determinista: mismo estado → mismo archivo)."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    # Verificar espacio en disco antes de escribir
    try:
        import shutil
        required_space = len(json.dumps(manifest, indent=2, sort_keys=True)) * 2  # 2x margen
        free_space = shutil.disk_usage(DATA_DIR).free
        if free_space < required_space:
            log.error(f"Espacio en disco insuficiente: {free_space} bytes libres, {required_space} bytes requeridos")
            raise OSError("Espacio en disco insuficiente")
    except Exception as e:
        log.error(f"Error verificando espacio en disco: {e}")
        raise

    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def index_documents(force: bool = False) -> dict:
    """Indexa todos los documentos en data/documentos/.
    - Archivos nuevos → chunk + embed
    - Archivos modificados (SHA-256 ≠) → re-indexa
    - Archivos sin cambios → no toca (idempotente)
    - Archivos eliminados → borra chunks de ChromaDB
    Retorna dict con estadísticas.
    """
    if not _chromadb_available():
        return {"error": "chromadb no instalado. pip install chromadb"}

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest() if not force else {"indexed_at": None, "total_documents": 0, "total_chunks": 0, "files": {}}
    collection = _get_collection()

    current_files = {}
    for f in DOCS_DIR.rglob("*"):
        if f.is_file() and not f.name.startswith("."):
            rel = str(f.relative_to(DOCS_DIR))
            current_files[rel] = _sha256(f)

    stats = {"new": 0, "modified": 0, "unchanged": 0, "deleted": 0, "chunks_added": 0}

    # Detectar eliminados
    for rel_path in list(manifest.get("files", {}).keys()):
        if rel_path not in current_files:
            try:
                collection.delete(where={"source": rel_path})
                del manifest["files"][rel_path]
                stats["deleted"] += 1
            except Exception as e:
                log.warning(f"Error eliminando {rel_path}: {e}")

    # Detectar nuevos/modificados
    for rel_path, file_hash in current_files.items():
        existing = manifest.get("files", {}).get(rel_path, {})
        if existing.get("sha256") == file_hash and not force:
            stats["unchanged"] += 1
            continue

        is_modified = rel_path in manifest.get("files", {})
        if is_modified:
            stats["modified"] += 1
            # Borrar chunks viejos antes de re-indexar
            with contextlib.suppress(Exception):
                collection.delete(where={"source": rel_path})
        else:
            stats["new"] += 1

        # Leer y chunkear
        try:
            filepath = DOCS_DIR / rel_path
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            log.error(f"Error crítico leyendo {rel_path}: {e}")
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        # Preparar para ChromaDB
        ids = [f"{rel_path}_{i}" for i in range(len(chunks))]
        metadatas = [{
            "source": rel_path,
            "chunk_index": i,
            "total_chunks": len(chunks),
            "sha256": file_hash,
            "indexed_at": datetime.now().isoformat(),
        } for i in range(len(chunks))]

        try:
            collection.add(documents=chunks, ids=ids, metadatas=metadatas)
            stats["chunks_added"] += len(chunks)
        except Exception as e:
            log.error(f"Error crítico indexando {rel_path}: {e}")
            continue

        manifest["files"][rel_path] = {
            "sha256": file_hash,
            "chunks": len(chunks),
            "indexed_at": datetime.now().isoformat(),
        }

    manifest["indexed_at"] = datetime.now().isoformat()
    manifest["total_documents"] = len(manifest["files"])
    manifest["total_chunks"] = stats["chunks_added"]  # solo nuevos/modificados
    save_manifest(manifest)

    return stats


# ============================================================
# Consulta (determinista: misma pregunta + mismo índice → misma respuesta)
# ============================================================

def query(question: str, top_k: int = TOP_K) -> list[dict]:
    """Busca los chunks más relevantes para una pregunta.
    Retorna lista de {content, source, chunk_index, similarity}.
    """
    if not _chromadb_available():
        return []

    try:
        collection = _get_collection()
        results = collection.query(
            query_texts=[question],
            n_results=min(top_k, 10),
        )
    except Exception as e:
        log.error(f"Error crítico consultando ChromaDB: {e}")
        return []

    if not results or not results.get("documents") or not results["documents"][0]:
        return []

    output = []
    docs = results["documents"][0]
    metas = results["metadatas"][0] if results.get("metadatas") else []
    distances = results.get("distances", [[]])[0]

    for i, doc in enumerate(docs):
        meta = metas[i] if i < len(metas) else {}
        dist = distances[i] if i < len(distances) else 0

        # ChromaDB usa distancia L2 por defecto; convertir a similitud aproximada
        similarity = 1.0 / (1.0 + dist) if dist > 0 else 1.0

        if similarity < SIMILARITY_THRESHOLD:
            continue

        output.append({
            "content": doc,
            "source": meta.get("source", "unknown"),
            "chunk_index": meta.get("chunk_index", 0),
            "similarity": round(similarity, 4),
        })

    return output


def get_sources(results: list[dict]) -> list[dict]:
    """Extrae fuentes únicas de los resultados de query()."""
    seen = set()
    sources = []
    for r in results:
        src = r.get("source", "unknown")
        if src not in seen:
            seen.add(src)
            sources.append({"source": src, "chunks_used": 1})
        else:
            for s in sources:
                if s["source"] == src:
                    s["chunks_used"] += 1
    return sources


def rag_enabled() -> bool:
    """Verifica si RAG está configurado y disponible."""
    return CONFIG.get("rag", {}).get("enabled", False) and _chromadb_available() and DOCS_DIR.exists()
