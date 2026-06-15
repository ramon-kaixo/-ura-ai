import logging
import threading
from datetime import datetime
from typing import Optional

from core.config import UraConfig

log = logging.getLogger("ura.qdrant")

COLECCION_INCIDENTES = "incidente_record"
VECTOR_SIZE = 7

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
