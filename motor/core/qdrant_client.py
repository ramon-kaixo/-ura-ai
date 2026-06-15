import json, logging
from pathlib import Path
from datetime import datetime
from typing import Optional
from core.config import UraConfig

log = logging.getLogger("ura.qdrant")

class QdrantClient:
    _instancia: Optional["QdrantClient"] = None

    def __init__(self, config: UraConfig):
        self.config = config
        self.disponible = False
        self._cliente = None
        self._conectar()

    def _conectar(self):
        try:
            from qdrant_client import QdrantClient as QC
            from qdrant_client.http import models
            self._cliente = QC(host=self.config.qdrant_host, port=self.config.qdrant_port, timeout=3)
            self._cliente.get_collections()
            self.disponible = True
            log.info("qdrant conectado")
        except Exception as e:
            log.warning("qdrant no disponible: %s", e)
            self.disponible = False

    def health(self) -> bool:
        if not self.disponible or not self._cliente:
            return False
        try:
            self._cliente.get_collections()
            return True
        except Exception:
            self.disponible = False
            return False

    def guardar_incidente(self, incidente: dict) -> bool:
        if not self.disponible or not self._cliente:
            return False
        try:
            from qdrant_client.http import models
            from qdrant_client.http.exceptions import UnexpectedResponse
            collection = "incidente_record"
            try:
                self._cliente.get_collection(collection)
            except UnexpectedResponse:
                self._cliente.recreate_collection(
                    collection_name=collection,
                    vectors_config=models.VectorParams(size=7, distance=models.Distance.COSINE),
                )
            payload = {
                "timestamp_inicio": incidente.get("ts", datetime.utcnow().isoformat()),
                "timestamp_resolucion": incidente.get("ts_resolucion", ""),
                "tipo_incidencia": incidente.get("tipo", "Unknown"),
                "subtipo": incidente.get("subtipo", ""),
                "resumen": incidente.get("resumen", ""),
                "impacto_memoria": incidente.get("impacto_memoria", [0.0]*7),
                "schema_version": self.config.schema_version,
                "hw_ok": incidente.get("hw_ok", True),
                "hw_issues": incidente.get("hw_issues", []),
            }
            self._cliente.upsert(
                collection_name=collection,
                points=[models.PointStruct(id=abs(hash(payload["timestamp_inicio"])),
                                            vector=payload["impacto_memoria"],
                                            payload=payload)]
            )
            return True
        except Exception as e:
            log.error("error guardar incidente: %s", e)
            return False

    def buscar_incidentes(self, vector: list, limit: int = 5) -> list:
        if not self.disponible or not self._cliente:
            return []
        try:
            from qdrant_client.http.exceptions import UnexpectedResponse
            try:
                r = self._cliente.search(
                    collection_name="incidente_record",
                    query_vector=vector,
                    limit=limit,
                )
                return [p.payload for p in r if hasattr(p, "payload")]
            except UnexpectedResponse:
                return []
        except Exception as e:
            log.error("error buscar incidentes: %s", e)
            return []

    @classmethod
    def instancia(cls, config: UraConfig) -> "QdrantClient":
        if cls._instancia is None:
            cls._instancia = cls(config)
        return cls._instancia
