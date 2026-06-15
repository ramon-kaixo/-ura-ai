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
            self._cliente = QC(host=self.config.qdrant_host, port=self.config.qdrant_port, timeout=3)
            self._cliente.get_collections()
            self.disponible = True
            self._modo_rest = False
            self._asegurar_coleccion()
            log.info("qdrant conectado (cliente nativo)")
        except Exception:
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
            except Exception:
                pass
            log.warning("qdrant no disponible")

    def _asegurar_coleccion(self):
        try:
            if getattr(self, "_modo_rest", False):
                import requests
                url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/incidente_record"
                r = requests.get(url, timeout=3)
                if r.status_code == 404:
                    r2 = requests.put(url, json={"vectors": {"size": 7, "distance": "Cosine"},
                                                  "on_disk_payload": True}, timeout=5)
                    if r2.status_code in (200, 201):
                        log.info("coleccion incidente_record creada (REST)")
            else:
                from qdrant_client.http.exceptions import UnexpectedResponse
                try:
                    self._cliente.get_collection("incidente_record")
                except UnexpectedResponse:
                    from qdrant_client.http import models
                    self._cliente.recreate_collection(
                        collection_name="incidente_record",
                        vectors_config=models.VectorParams(size=7, distance=models.Distance.COSINE),
                    )
                    log.info("coleccion incidente_record creada (nativo)")
        except Exception as e:
            log.warning("no se pudo asegurar coleccion: %s", e)

    def health(self) -> bool:
        if not self.disponible:
            return False
        if getattr(self, "_modo_rest", False):
            return True
        if not self._cliente:
            return False
        try:
            self._cliente.get_collections()
            return True
        except Exception:
            self.disponible = False
            return False

    def guardar_incidente(self, incidente: dict) -> bool:
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
                collection_name="incidente_record",
                points=[models.PointStruct(id=abs(hash(payload["timestamp_inicio"])),
                                            vector=payload["impacto_memoria"],
                                            payload=payload)]
            )
            return True
        except Exception as e:
            log.error("error guardar incidente: %s", e)
            return False

    def _build_payload(self, incidente: dict) -> dict:
        return {
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

    def _guardar_rest(self, incidente: dict) -> bool:
        try:
            import requests
            payload = self._build_payload(incidente)
            point = {
                "id": abs(hash(payload["timestamp_inicio"])),
                "vector": payload["impacto_memoria"],
                "payload": payload,
            }
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/incidente_record/points"
            r = requests.put(url, json={"points": [point]}, timeout=5)
            return r.status_code in (200, 201)
        except Exception as e:
            log.error("error guardar incidente (REST): %s", e)
            return False

    def buscar_incidentes(self, vector: list = None, limit: int = 10) -> list:
        if not self.disponible:
            return []
        if getattr(self, "_modo_rest", False):
            return self._buscar_rest(limit)
        if not self._cliente:
            return []
        try:
            r = self._cliente.scroll(collection_name="incidente_record", limit=limit)
            pts = r[0] if r else []
            return [p.payload for p in pts if hasattr(p, "payload")]
        except Exception as e:
            log.error("error buscar incidentes: %s", e)
            return []

    def _buscar_rest(self, limit: int = 5) -> list:
        try:
            import requests
            url = f"http://{self.config.qdrant_host}:{self.config.qdrant_port}/collections/incidente_record/points/scroll"
            r = requests.post(url, json={"limit": limit}, timeout=5)
            if r.status_code == 200:
                return [p.get("payload", {}) for p in r.json().get("result", {}).get("points", [])]
        except: pass
        return []

    @classmethod
    def instancia(cls, config: UraConfig) -> "QdrantClient":
        if cls._instancia is None:
            cls._instancia = cls(config)
        return cls._instancia
