import asyncio
import hashlib
import logging
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from typing import Optional

import httpx

from motor.core.config import UraConfig

log = logging.getLogger("ura.qdrant")

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
        """Intenta conectar vía cliente nativo; fallback a REST."""
        try:
            from qdrant_client import QdrantClient as QC

            self._cliente = QC(host=self.config.qdrant_host, port=self.config.qdrant_port, timeout=3)
            self._cliente.get_collections()
            self.disponible = True
            self._modo_rest = False
            self._asegurar_coleccion()
            self._asegurar_coleccion_documentos()
            self._asegurar_coleccion_transacciones()
            log.info("qdrant conectado (cliente nativo)")
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
                    log.info("qdrant conectado (REST fallback)")
                    return
            except Exception as e_rest:
                log.warning("fallback REST qdrant falló: %s", e_rest)
            log.warning("qdrant no disponible en %s:%s", self.config.qdrant_host, self.config.qdrant_port)

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
                        log.info("coleccion %s creada (REST)", COLECCION_INCIDENTES)
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
                    log.info("coleccion %s creada (nativo)", COLECCION_INCIDENTES)
        except Exception as e:
            log.warning("no se pudo asegurar coleccion: %s", e)

    def _asegurar_coleccion_documentos(self) -> None:
        """Crea la colección de documentos si no existe (768-d, Cosine)."""
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
                        log.info("coleccion %s creada (REST)", COLECCION_DOCUMENTOS)
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
                    log.info("coleccion %s creada (nativo)", COLECCION_DOCUMENTOS)
        except Exception as e:
            log.warning("no se pudo asegurar coleccion documentos: %s", e)

    def _asegurar_coleccion_transacciones(self) -> None:
        """Crea la colección de transacciones si no existe (768-d, Cosine)."""
        try:
            if getattr(self, "_modo_rest", False):
                url = (
                    f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_TRANSACCIONES}"
                )
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
                        log.info("coleccion %s creada (REST)", COLECCION_TRANSACCIONES)
            else:
                from qdrant_client.http.exceptions import UnexpectedResponse

                try:
                    self._cliente.get_collection(COLECCION_TRANSACCIONES)
                except UnexpectedResponse:
                    from qdrant_client.http import models

                    self._cliente.recreate_collection(
                        collection_name=COLECCION_TRANSACCIONES,
                        vectors_config=models.VectorParams(size=VECTOR_SIZE_EMBEDDING, distance=models.Distance.COSINE),
                    )
                    log.info("coleccion %s creada (nativo)", COLECCION_TRANSACCIONES)
        except Exception as e:
            log.warning("no se pudo asegurar coleccion transacciones: %s", e)

    async def generar_embedding_async(self, texto: str) -> list[float]:
        """Versión async con semáforo y httpx."""
        async with self.embedding_semaphore:
            result = await self.generar_embeddings_batch_async([texto])
            if not result or all(abs(v) < 1e-6 for v in result[0]):
                log.error("generar_embedding_async returned zero vector for '%s...'", texto[:50])
                return [0.0] * VECTOR_SIZE_EMBEDDING
            return result[0]

    async def generar_embeddings_batch_async(self, textos: list[str]) -> list[list[float]]:
        """Async version of generar_embeddings_batch using httpx.AsyncClient."""
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.post(
                    f"{ollama_url}/api/embed",
                    json={"model": MODELO_EMBEDDING, "input": textos},
                )
                if r.status_code == 200:
                    return r.json()["embeddings"]
        except Exception:
            pass
        resultados = []
        for t in textos:
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"{ollama_url}/api/embeddings",
                        json={"model": MODELO_EMBEDDING, "prompt": t},
                    )
                    r.raise_for_status()
                    resultados.append(r.json()["embedding"])
            except Exception as e:
                log.exception("error generando embedding (old API): %s", e)
                log.warning("Fallback zero-vector para texto: '%s...'", t[:50])
                resultados.append([0.0] * VECTOR_SIZE_EMBEDDING)
        return resultados

    # Sync wrapper — hilo secundario si el loop ya está corriendo
    def generar_embedding(self, texto: str) -> list[float]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.generar_embedding_async(texto))
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(asyncio.run, self.generar_embedding_async(texto))
            return future.result()

    def generar_embeddings_batch(self, textos: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos.
        Soporta API nueva (/api/embed) y antigua (/api/embeddings, Ollama <0.3.0).
        """
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        # Intentar API nueva (batch)
        try:
            r = httpx.post(
                f"{ollama_url}/api/embed",
                json={"model": MODELO_EMBEDDING, "input": textos},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()["embeddings"]
        except Exception as e:
            log.debug("Ollama new API /api/embed falló: %s", e)

        # Fallback: API antigua (una llamada por texto, sin batch)
        resultados = []
        for t in textos:
            try:
                r = httpx.post(
                    f"{ollama_url}/api/embeddings",
                    json={"model": MODELO_EMBEDDING, "prompt": t},
                    timeout=30,
                )
                r.raise_for_status()
                resultados.append(r.json()["embedding"])
            except Exception as e:
                log.exception("error generando embedding (old API): %s", e)
                resultados.append([0.0] * VECTOR_SIZE_EMBEDDING)
        return resultados

    def guardar_documento(
        self,
        doc_id: str,
        texto: str,
        metadata: dict | None = None,
        collection: str = COLECCION_DOCUMENTOS,
    ) -> bool:
        """Genera embedding y guarda un documento en Qdrant."""
        return self._guardar_documentos([(doc_id, texto, metadata or {})], collection) > 0

    def guardar_documentos_batch(
        self,
        docs: list[tuple[str, str, dict]],
        collection: str = COLECCION_DOCUMENTOS,
    ) -> int:
        """Guarda múltiples documentos en batch (más eficiente).

        Args:
            docs: lista de (doc_id, texto, metadata)
            collection: colección destino

        Returns:
            cantidad de documentos guardados exitosamente

        """
        return self._guardar_documentos(docs, collection)

    def _guardar_documentos(self, docs: list[tuple[str, str, dict]], collection: str = COLECCION_DOCUMENTOS) -> int:
        """Implementación compartida para guardar uno o varios documentos."""
        if not self.disponible or not docs:
            return 0
        textos = [d[1] for d in docs]
        vectores = self.generar_embeddings_batch(textos)
        puntos = []
        for i, (doc_id, texto, metadata) in enumerate(docs):
            payload = {"texto": texto[:5000], "id": doc_id, **metadata}
            pid = (
                int(hashlib.sha256(doc_id.encode()).hexdigest()[:15], 16) % (2**63)
                if doc_id
                else int(hashlib.sha256((texto[:100]).encode()).hexdigest()[:15], 16) % (2**63)
            )
            puntos.append({"id": pid, "vector": vectores[i], "payload": payload})
        if getattr(self, "_modo_rest", False):
            return self._guardar_documentos_rest(puntos, collection)
        if not self._cliente:
            return 0
        try:
            from qdrant_client.http import models

            pts = [models.PointStruct(id=p["id"], vector=p["vector"], payload=p["payload"]) for p in puntos]
            self._cliente.upsert(collection_name=collection, points=pts)
            return len(pts)
        except Exception as e:
            log.exception("error guardar documentos batch: %s", e)
            return 0

    def _guardar_documentos_rest(self, puntos: list[dict], collection: str = COLECCION_DOCUMENTOS) -> int:
        try:
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points"
            r = httpx.put(url, json={"points": puntos}, timeout=10)
            return len(puntos) if r.status_code in (200, 201) else 0
        except Exception as e:
            log.exception("error guardar documentos batch (REST): %s", e)
            return 0

    def buscar_por_similitud(self, query_vector: list, collection: str = COLECCION_DOCUMENTOS, limit: int = 10) -> list:
        """Busca puntos por similitud coseno en la colección especificada."""
        if not self.disponible:
            return []
        if getattr(self, "_modo_rest", False):
            return self._buscar_similitud_rest(query_vector, collection, limit)
        if not self._cliente:
            return []
        try:
            r = self._cliente.query_points(
                collection_name=collection,
                query=query_vector,
                limit=limit,
            )
            return [{"payload": p.payload, "score": p.score} for p in (r.points or [])]
        except Exception as e:
            log.exception("error buscar por similitud: %s", e)
            return []

    def _buscar_similitud_rest(self, query_vector: list, collection: str, limit: int) -> list:
        try:
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points/search"
            r = httpx.post(url, json={"vector": query_vector, "limit": limit}, timeout=5)
            if r.status_code == 200:
                return [
                    {"payload": p.get("payload", {}), "score": p.get("score", 0)} for p in r.json().get("result", [])
                ]
        except Exception as e:
            log.warning("buscar_similitud_rest falló: %s", e)
        return []

    def buscar_documentos(self, query_texto: str, limit: int = 10) -> list:
        """Conveniencia: genera embedding de la consulta y busca documentos similares."""
        vector = self.generar_embedding(query_texto)
        return self.buscar_por_similitud(vector, COLECCION_DOCUMENTOS, limit)

    def eliminar_por_filtro(self, filtro: dict, collection: str = COLECCION_DOCUMENTOS) -> bool:
        """Elimina puntos que coinciden con un filtro (ej: {"source": "path/to/file"})."""
        if not self.disponible:
            return False
        if getattr(self, "_modo_rest", False):
            return self._eliminar_por_filtro_rest(filtro, collection)
        if not self._cliente:
            return False
        try:
            from qdrant_client.http import models

            self._cliente.delete(
                collection_name=collection,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(key=k, match=models.MatchValue(value=v)) for k, v in filtro.items()
                        ],
                    ),
                ),
            )
            return True
        except Exception as e:
            log.exception("error eliminar por filtro: %s", e)
            return False

    def _eliminar_por_filtro_rest(self, filtro: dict, collection: str) -> bool:
        try:
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points/delete"
            must = [{"key": k, "match": {"value": v}} for k, v in filtro.items()]
            r = httpx.post(url, json={"filter": {"must": must}}, timeout=5)
            return r.status_code in (200, 201)
        except Exception as e:
            log.warning("eliminar_rest falló: %s", e)
            return False

    def health(self) -> bool:
        """Devuelve True si Qdrant responde."""
        if not self.disponible:
            return False
        if getattr(self, "_modo_rest", False):
            return True
        if not self._cliente:
            return False
        try:
            self._cliente.get_collections()
            return True
        except Exception as e:
            log.warning("health check qdrant falló: %s", e)
            self.disponible = False
            return False

    def guardar_incidente(self, incidente: dict) -> bool:
        """Guarda un incidente en Qdrant."""
        if not self.disponible:
            return False
        if getattr(self, "_modo_rest", False):
            return self._guardar_rest(incidente)
        if not self._cliente:
            return False
        try:
            from qdrant_client.http import models

            payload = self._build_payload(incidente)
            self._cliente.upsert(
                collection_name=COLECCION_INCIDENTES,
                points=[
                    models.PointStruct(
                        id=int(hashlib.sha256(payload["timestamp_inicio"].encode()).hexdigest()[:15], 16) % (2**63),
                        vector=payload["impacto_memoria"],
                        payload=payload,
                    ),
                ],
            )
            return True
        except Exception as e:
            log.exception("error guardar incidente: %s", e)
            return False

    def _build_payload(self, incidente: dict) -> dict:
        """Construye el payload estructurado para Qdrant (schema v3.1)."""
        return {
            "timestamp_inicio": incidente.get("ts", datetime.now(UTC).isoformat()),
            "timestamp_resolucion": incidente.get("ts_resolucion", ""),
            "tipo_incidencia": incidente.get("tipo", "Unknown"),
            "subtipo": incidente.get("subtipo", ""),
            "resumen": incidente.get("resumen", ""),
            "impacto_memoria": incidente.get("impacto_memoria", [0.0] * VECTOR_SIZE),
            "schema_version": self.config.schema_version,
            "hw_ok": incidente.get("hw_ok", True),
            "hw_issues": incidente.get("hw_issues", []),
            "affected_resources": incidente.get("affected_resources", {}),
            "cleanup_cmd": incidente.get("cleanup_cmd", ""),
            "pre_state": incidente.get("pre_state", {}),
            "trace": incidente.get("trace", ""),
            "origin_node": incidente.get("origin_node", "ASUS"),
            "dependency_chain": incidente.get("dependency_chain", []),
            "exit_code": incidente.get("exit_code", -1),
            "signal": incidente.get("signal", 0),
            "oom_killed": incidente.get("oom_killed", False),
            "segfault": incidente.get("segfault", False),
        }

    def _guardar_rest(self, incidente: dict) -> bool:
        """Guarda incidente vía REST (fallback)."""
        try:
            payload = self._build_payload(incidente)
            point = {
                "id": int(hashlib.sha256(payload["timestamp_inicio"].encode()).hexdigest()[:15], 16) % (2**63),
                "vector": payload["impacto_memoria"],
                "payload": payload,
            }
            url = (
                f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}/points"
            )
            r = httpx.put(url, json={"points": [point]}, timeout=5)
            return r.status_code in (200, 201)
        except Exception as e:
            log.exception("error guardar incidente (REST): %s", e)
            return False

    def buscar_incidentes(self, vector: list | None = None, limit: int = 10) -> list:
        """Busca incidentes almacenados en Qdrant."""
        if not self.disponible:
            return []
        if getattr(self, "_modo_rest", False):
            return self._buscar_rest(limit)
        if not self._cliente:
            return []
        try:
            r = self._cliente.scroll(collection_name=COLECCION_INCIDENTES, limit=limit)
            pts = r[0] if r else []
            return [p.payload for p in pts if hasattr(p, "payload")]
        except Exception as e:
            log.exception("error buscar incidentes: %s", e)
            return []

    def _buscar_rest(self, limit: int = 5) -> list:
        """Busca incidentes vía REST (fallback)."""
        try:
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}/points/scroll"
            r = httpx.post(url, json={"limit": limit}, timeout=5)
            if r.status_code == 200:
                return [p.get("payload", {}) for p in r.json().get("result", {}).get("points", [])]
        except Exception as e:
            log.warning("buscar_rest falló: %s", e)
        return []

    @classmethod
    def instancia(cls, config: UraConfig) -> "QdrantClient":
        """Singleton thread-safe."""
        with cls._lock:
            if cls._instancia is None:
                cls._instancia = cls(config)
        return cls._instancia


class URAQdrantClient:
    """Cliente Qdrant asíncrono con connection pooling (HTTP/2 keep-alive ready).

    Uso:
        qdrant = URAQdrantClient()
        resultados = await qdrant.buscar_vectores("coleccion", vector, limite=5)
        await qdrant.close()
    """

    def __init__(self, base_url: str = "http://127.0.0.1:6333", timeout: float = 10.0):
        self.base_url = base_url
        self.timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Inicialización perezosa con pool de conexiones reutilizable."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                limits=httpx.Limits(max_keepalive_connections=20, max_connections=100),
            )
        return self._client

    async def buscar_vectores(
        self,
        coleccion: str,
        vector: list,
        limite: int = 5,
    ) -> dict:
        """Búsqueda vectorial asíncrona sin bloquear el event-loop."""
        client = await self._get_client()
        payload = {"vector": vector, "limit": limite, "with_payload": True}
        try:
            response = await client.post(
                f"/collections/{coleccion}/points/search",
                json=payload,
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            log.error("Error HTTP en Qdrant (%s): %s", e.response.status_code, e.response.text)
            return {"result": []}
        except httpx.RequestError as e:
            log.error("Fallo de red al conectar con Qdrant: %s", e)
            return {"result": []}

    async def upsert_puntos(
        self,
        coleccion: str,
        puntos: list[dict],
    ) -> int:
        """Inserta o actualiza puntos en Qdrant."""
        client = await self._get_client()
        try:
            response = await client.put(
                f"/collections/{coleccion}/points",
                json={"points": puntos},
            )
            response.raise_for_status()
            return len(puntos)
        except Exception as e:
            log.error("Error upsert en Qdrant: %s", e)
            return 0

    async def close(self) -> None:
        """Cierre ordenado del pool de conexiones."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ─── Búsqueda Híbrida: Dense + Sparse + RRF ───

    async def asegurar_coleccion_hibrida(self, coleccion: str) -> bool:
        """Crea o verifica una colección con soporte dense+sparse."""
        client = await self._get_client()
        try:
            resp = await client.get(f"/collections/{coleccion}")
            if resp.status_code == 200:
                return True
        except Exception:
            pass
        payload = {
            "vectors": {"size": VECTOR_SIZE_EMBEDDING, "distance": "Cosine"},
            "sparse_vectors": {"bm25": {"index": {"on_disk": True}, "modifier": "idf"}},
        }
        try:
            resp = await client.put(f"/collections/{coleccion}", json=payload)
            return resp.status_code in (200, 201)
        except Exception as e:
            log.error("Error creando colección híbrida: %s", e)
            return False

    async def buscar_hibrido(
        self,
        coleccion: str,
        texto_query: str,
        vector_denso: list,
        limite: int = 10,
    ) -> list[dict]:
        """Búsqueda híbrida dense+sparse con RRF."""
        client = await self._get_client()
        sparse = generar_sparse_vector(texto_query)

        # Prefetch fusionado con RRF
        payload = {
            "prefetch": [
                {"query": vector_denso, "using": "default", "limit": limite * 4},
                {
                    "query": {"indices": sparse["indices"], "values": sparse["values"]},
                    "using": "bm25",
                    "limit": limite * 4,
                },
            ],
            "query": {"fusion": "rrf"},
            "limit": limite,
            "with_payload": True,
        }
        try:
            resp = await client.post(f"/collections/{coleccion}/points/search", json=payload)
            resp.raise_for_status()
            return resp.json().get("result", [])
        except Exception as e:
            log.warning("Búsqueda híbrida falló, fallback a densa: %s", e)
            fallback = await self.buscar_vectores(coleccion, vector_denso, limite)
            return fallback.get("result", [])
