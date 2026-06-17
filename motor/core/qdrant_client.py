import logging
import os
import threading
from datetime import datetime
from typing import Optional

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
                import requests
                r = requests.get(f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections",
                                 timeout=3)
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
                import requests
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}"
                r = requests.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = requests.put(url, json={"vectors": {"size": VECTOR_SIZE, "distance": "Cosine"},
                                                  "on_disk_payload": True}, timeout=5)
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
                import requests
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_DOCUMENTOS}"
                r = requests.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = requests.put(url, json={"vectors": {"size": VECTOR_SIZE_EMBEDDING, "distance": "Cosine"},
                                                  "on_disk_payload": True}, timeout=5)
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
                import requests
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_TRANSACCIONES}"
                r = requests.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = requests.put(url, json={"vectors": {"size": VECTOR_SIZE_EMBEDDING, "distance": "Cosine"},
                                                  "on_disk_payload": True}, timeout=5)
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

    def generar_embedding(self, texto: str) -> list[float]:
        """Genera embedding vía Ollama usando nomic-embed-text."""
        try:
            return self.generar_embeddings_batch([texto])[0]
        except Exception as e:
            log.exception("error generando embedding: %s", e)
            return [0.0] * VECTOR_SIZE_EMBEDDING

    def generar_embeddings_batch(self, textos: list[str]) -> list[list[float]]:
        """Genera embeddings para múltiples textos.
        Soporta API nueva (/api/embed) y antigua (/api/embeddings, Ollama <0.3.0).
        """
        import requests
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        # Intentar API nueva (batch)
        try:
            r = requests.post(
                f"{ollama_url}/api/embed",
                json={"model": MODELO_EMBEDDING, "input": textos},
                timeout=30,
            )
            if r.status_code == 200:
                return r.json()["embeddings"]
        except Exception:
            pass

        # Fallback: API antigua (una llamada por texto, sin batch)
        resultados = []
        for t in textos:
            try:
                r = requests.post(
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

    def guardar_documento(self, doc_id: str, texto: str, metadata: dict | None = None, collection: str = COLECCION_DOCUMENTOS) -> bool:
        """Genera embedding y guarda un documento en Qdrant."""
        return self._guardar_documentos([(doc_id, texto, metadata or {})], collection) > 0

    def guardar_documentos_batch(self, docs: list[tuple[str, str, dict]], collection: str = COLECCION_DOCUMENTOS) -> int:
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
            pid = abs(hash(doc_id)) if doc_id else abs(hash(texto[:100]))
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
            import requests
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points"
            r = requests.put(url, json={"points": puntos}, timeout=10)
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
            import requests
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points/search"
            r = requests.post(url, json={"vector": query_vector, "limit": limit}, timeout=5)
            if r.status_code == 200:
                return [{"payload": p.get("payload", {}), "score": p.get("score", 0)}
                        for p in r.json().get("result", [])]
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
                        must=[models.FieldCondition(key=k, match=models.MatchValue(value=v))
                              for k, v in filtro.items()],
                    ),
                ),
            )
            return True
        except Exception as e:
            log.exception("error eliminar por filtro: %s", e)
            return False

    def _eliminar_por_filtro_rest(self, filtro: dict, collection: str) -> bool:
        try:
            import requests
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{collection}/points/delete"
            must = [{"key": k, "match": {"value": v}} for k, v in filtro.items()]
            r = requests.post(url, json={"filter": {"must": must}}, timeout=5)
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
                points=[models.PointStruct(id=abs(hash(payload["timestamp_inicio"])),
                                            vector=payload["impacto_memoria"],
                                            payload=payload)],
            )
            return True
        except Exception as e:
            log.exception("error guardar incidente: %s", e)
            return False

    def _build_payload(self, incidente: dict) -> dict:
        """Construye el payload estructurado para Qdrant."""
        return {
            "timestamp_inicio": incidente.get("ts", datetime.utcnow().isoformat()),
            "timestamp_resolucion": incidente.get("ts_resolucion", ""),
            "tipo_incidencia": incidente.get("tipo", "Unknown"),
            "subtipo": incidente.get("subtipo", ""),
            "resumen": incidente.get("resumen", ""),
            "impacto_memoria": incidente.get("impacto_memoria", [0.0]*VECTOR_SIZE),
            "schema_version": self.config.schema_version,
            "hw_ok": incidente.get("hw_ok", True),
            "hw_issues": incidente.get("hw_issues", []),
        }

    def _guardar_rest(self, incidente: dict) -> bool:
        """Guarda incidente vía REST (fallback)."""
        try:
            import requests
            payload = self._build_payload(incidente)
            point = {
                "id": abs(hash(payload["timestamp_inicio"])),
                "vector": payload["impacto_memoria"],
                "payload": payload,
            }
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}/points"
            r = requests.put(url, json={"points": [point]}, timeout=5)
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
            import requests
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/{COLECCION_INCIDENTES}/points/scroll"
            r = requests.post(url, json={"limit": limit}, timeout=5)
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
