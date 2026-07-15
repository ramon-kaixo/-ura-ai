#!/usr/bin/env python3
"""Memory Engine — RAG (Retrieval-Augmented Generation) para URA.
Indexa documentos locales en Qdrant y enriquece consultas con contexto.
Determinista: sin variables globales, todo el estado en disco.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import contextlib
import hashlib
import json
import logging
from datetime import UTC, datetime

from core.config_manager import CONFIG
from motor.core.config import UraConfig
from motor.core.llm import generate as llm_generate
from motor.core.qdrant_client import QdrantClient

log = logging.getLogger(__name__)

RAG_CONFIG = CONFIG.get("rag", {})
DATA_DIR = Path(CONFIG["paths"]["data"])
DOCS_DIR = DATA_DIR / "documentos"
MANIFEST_PATH = DATA_DIR / ".index_manifest.json"
CHUNK_SIZE = RAG_CONFIG.get("chunk_size", 500)
CHUNK_OVERLAP = RAG_CONFIG.get("chunk_overlap", 50)
TOP_K = RAG_CONFIG.get("top_k", 5)
SIMILARITY_THRESHOLD = RAG_CONFIG.get("threshold", 0.7)

_qdrant: QdrantClient | None = None


def _get_qdrant() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient.instancia(UraConfig.load())
    return _qdrant


def _sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
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


# ============================================================
# Indexación (determinista: mismo input → mismo índice)
# ============================================================


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        try:
            return json.loads(MANIFEST_PATH.read_text())
        except Exception as e:
            log.warning(f"Error cargando manifest: {e}")
    return {"indexed_at": None, "total_documents": 0, "total_chunks": 0, "files": {}}


def save_manifest(manifest: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    try:
        import shutil

        required_space = len(json.dumps(manifest, indent=2, sort_keys=True)) * 2
        free_space = shutil.disk_usage(DATA_DIR).free
        if free_space < required_space:
            log.error(f"Espacio en disco insuficiente: {free_space} bytes libres, {required_space} bytes requeridos")
            msg = "Espacio en disco insuficiente"
            raise OSError(msg)
    except Exception as e:
        log.exception(f"Error verificando espacio en disco: {e}")
        raise
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, sort_keys=True))


def index_documents(force: bool = False) -> dict:
    """Indexa todos los documentos en data/documentos/ en Qdrant.
    - Archivos nuevos → chunk + embed (vía Ollama)
    - Archivos modificados (SHA-256 ≠) → re-indexa
    - Archivos sin cambios → no toca (idempotente)
    - Archivos eliminados → borra chunks de Qdrant
    Retorna dict con estadísticas.
    """
    qdrant = _get_qdrant()
    if not qdrant.disponible:
        return {"error": "Qdrant no disponible"}

    DOCS_DIR.mkdir(parents=True, exist_ok=True)

    manifest = (
        load_manifest() if not force else {"indexed_at": None, "total_documents": 0, "total_chunks": 0, "files": {}}
    )

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
                qdrant.eliminar_por_filtro({"source": rel_path})
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
            with contextlib.suppress(Exception):
                qdrant.eliminar_por_filtro({"source": rel_path})
        else:
            stats["new"] += 1

        # Leer y chunkear
        try:
            filepath = DOCS_DIR / rel_path
            text = filepath.read_text(encoding="utf-8")
        except Exception as e:
            log.exception(f"Error crítico leyendo {rel_path}: {e}")
            continue

        chunks = _chunk_text(text)
        if not chunks:
            continue

        # Preparar batch para Qdrant
        now = datetime.now(UTC).isoformat()
        docs_batch = []
        for i, chunk_text in enumerate(chunks):
            doc_id = f"{rel_path}_{i}"
            metadata = {
                "source": rel_path,
                "chunk_index": i,
                "total_chunks": len(chunks),
                "sha256": file_hash,
                "indexed_at": now,
            }
            docs_batch.append((doc_id, chunk_text, metadata))

        try:
            guardados = qdrant.guardar_documentos_batch(docs_batch)
            stats["chunks_added"] += guardados
        except Exception as e:
            log.exception(f"Error crítico indexando {rel_path}: {e}")
            continue

        manifest["files"][rel_path] = {
            "sha256": file_hash,
            "chunks": len(chunks),
            "indexed_at": now,
        }

    manifest["indexed_at"] = datetime.now(UTC).isoformat()
    manifest["total_documents"] = len(manifest["files"])
    manifest["total_chunks"] = stats["chunks_added"]
    save_manifest(manifest)

    return stats


# ============================================================
# Consulta (determinista: misma pregunta + mismo índice → misma respuesta)
# ============================================================


def query(question: str, top_k: int = TOP_K) -> list[dict]:
    """Busca los chunks más relevantes para una pregunta en Qdrant.
    Retorna lista de {content, source, chunk_index, similarity}.
    """
    qdrant = _get_qdrant()
    if not qdrant.disponible:
        return []

    try:
        results = qdrant.buscar_documentos(question, limit=min(top_k, 10))
    except Exception as e:
        log.exception(f"Error crítico consultando Qdrant: {e}")
        return []

    output = []
    for r in results:
        payload = r.get("payload", {})
        score = r.get("score", 0)

        if score < SIMILARITY_THRESHOLD:
            continue

        output.append(
            {
                "content": payload.get("texto", ""),
                "source": payload.get("source", "unknown"),
                "chunk_index": payload.get("chunk_index", 0),
                "similarity": round(score, 4),
            },
        )

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
    if not CONFIG.get("rag", {}).get("enabled", False):
        return False
    qdrant = _get_qdrant()
    return qdrant.disponible and DOCS_DIR.exists()


def _build_context(results: list[dict], max_chars: int = 8000) -> str:
    """Construye un string de contexto a partir de los resultados de query()."""
    parts: list[str] = []
    for i, r in enumerate(results):
        content = r.get("content", "")
        if not content:
            continue
        source = r.get("source", "unknown")
        score = r.get("similarity", 0)
        parts.append(f"[{i + 1}] (fuente: {source}, similitud: {score:.2f})\n{content}")
    result = "\n\n".join(parts)
    if len(result) > max_chars:
        result = result[:max_chars]
    return result


def _generate(context: str, question: str) -> str:
    """Wrapper temporal: delega en motor.core.llm.generate().
    Se eliminará cuando toda la migración esté validada."""
    if not context:
        return "No se encontraron documentos relevantes para generar una respuesta."
    prompt = (
        "Eres un asistente experto. Responde la pregunta basándote exclusivamente "
        "en el contexto proporcionado. Si el contexto no contiene la respuesta, "
        "di que no tienes información suficiente.\n\n"
        f"Contexto:\n{context}\n\n"
        f"Pregunta: {question}\n\n"
        "Respuesta:"
    )
    return llm_generate(prompt)


def ask(question: str, top_k: int | None = None) -> str:
    """RAG completo: recupera documentos relevantes y genera una respuesta.
    Retorna la respuesta generada por el LLM.
    """
    docs = query(question, top_k=top_k or TOP_K)
    context = _build_context(docs)
    return _generate(context, question)
