
import asyncio
import hashlib
import logging
import re
import threading
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Optional

import httpx

from motor.core.config import UraConfig
from motor.core.llm import embed as llm_embed
from motor.core.llm import embed_async as llm_embed_async
from motor.core.state import DegradedMode

log = logging.getLogger("ura.qdrant")

def generar_sparse_vector(texto: str, max_tokens: int = 512) -> dict:
    """Genera sparse vector  (indices + valores TF) para búsqueda híbrida Qdrant."""
    tokens = re.findall(r"\w+", texto.lower())[:max_tokens]
    freqs = Counter(tokens)
    indices = [hash(t) % (2**31) for t in freqs]
    values = [f / len(tokens) for f in freqs.values()]
    return {"indices": indices, "values": values}

COLECCION_INCIDENTES = "incidente_record"
VECTOR_SIZE = 7
COLECCION_DOCUMENTOS = "ura_documents"
COLECCION_TRANSACCIONES = "ura_transacciones"
VECTOR_SIZE_EMBEDDING = 768
MODELO_EMBEDDING = "nomic-embed-text"

class QdrantClient:
    """Cliente para Qdrant con fallback REST automático."""
    
    _instancia: Optional["QdrantClient"] = None
    _lock: threading.Lock = threading.Lock()

    def __init__(self, config: UraConfig) -> None:
        self.config = config
        self.disponible = False
        self._cliente = None
        self.embedding_semaphore = asyncio.Semaphore(value=1)
        self._conectar()

    def _conectar(self) -> None:
        """Intenta conectar vía cliente nativo fallback a REST."""
        try:
            from qdrant_client import QdrantClient as QC
            
            self._cliente = QC(host=self.config.qdrant_host, port=self.config.qdrant_port, timeout=3)
            self._cliente.get_collections()
            self.disponible = True
            self._modo_rest = False
            self._asegurar_coleccion()
            self._asegurar_coleccion_documentos()
            self._asegurar_coleccion_transacciones()
            DegradedMode.instancia().mark_healthy("qdrant")
            log.info("qdrant conectado  (cliente nativo)")
        except Exception as e_nativo:
            log.debug("cliente nativo qdrant falló: %s", e_nativo)
            try:
                r = httpx.get(f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections", timeout=3)
                if r.status_code < 500:
                    self._cliente = None
                    self.disponible = True
                    self._modo_rest = True
                    self._asegurar_coleccion()
                    self._asegurar_coleccion_documentos()
                    self._asegurar_coleccion_transacciones()
                    DegradedMode.instancia().mark_healthy("qdrant")
                    log.info("qdrant conectado  (REST fallback)")
            except Exception as e_rest:
                log.warning("fallback REST qdrant falló: %s", e_rest)
            DegradedMode.instancia().mark_degraded("qdrant")
            log.warning("qdrant no disponible en  %s:%s", self.config.qdrant_host, self.config.qdrant_port)
            
    def _asegurar_coleccion(self) -> None:
        """Crea la colección de incidentes si no existe."""
        try:
            if getattr(self, "_modo_rest", False):
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}"
                r = httpx.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = httpx.put(
                        url,
                        json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"}, "on_disk_payload": True},
                        timeout=5,
                    )
                    if r2.status_code in (200, 201):
                        log.info("coleccion %s creada  (REST)", COLECCION_INCIDENTES)
            else:
                from qdrant_client.http.exceptions import UnexpectedResponse
                
                try:
                    self._cliente.get_collection(COLECCION_INCIDENTES)
                except UnexpectedResponse:
                    from qdrant_client.http import models
                    
                    self._cliente.recreate_collection(
                        collection_name=COLECCION_INCIDENTES,
                        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
                    )
                    log.info("coleccion %s creada  (nativo)", COLECCION_INCIDENTES)
        except Exception as e:
            log.warning("no se pudo asegurar coleccion: %s", e)
            
    def _asegurar_coleccion_documentos(self) -> None:
        """Crea la colección de documentos si no existe  (768-d, Cosine)."""
        try:
            if getattr(self, "_modo_rest", False):
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_DOCUMENTOS}"
                r = httpx.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = httpx.put(
                        url,
                        json={
                            "vectors": {"size": VECTOR_SIZE_EMBEDDING, "distance": "Cosine"},
                            "on_disk_payload": True,
                        },
                        timeout=5,
                    )
                    if r2.status_code in (200, 201):
                        log.info("coleccion %s creada  (REST)", COLECCION_DOCUMENTOS)
            else:
                from qdrant_client.http.exceptions import UnexpectedResponse
                
                try:
                    self._cliente.get_collection(COLECCION_DOCUMENTOS)
                except UnexpectedResponse:
                    from qdrant_client.http import models
                    
                    self._cliente.recreate_collection(
                        collection_name=COLECCION_DOCUMENTOS,
                        vectors_config=models.VectorParams(size=VECTOR_SIZE_EMBEDDING, distance=models.Distance.COSINE),
                    )
