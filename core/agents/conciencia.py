"""Memoria unificada del sistema. Archivo: .nervioso/conciencia.json."""

import json
import logging
import threading
from datetime import UTC, datetime

from core.agents.constants import NERVIOSO

log = logging.getLogger("ura.multi_agent.conciencia")


class Conciencia:
    """Memoria unificada del sistema. Archivo: .nervioso/conciencia.json."""

    PATH = NERVIOSO / "conciencia.json"
    _lock = threading.Lock()

    @classmethod
    def leer(cls) -> dict:
        if cls.PATH.exists():
            try:
                return json.loads(cls.PATH.read_text())
            except Exception:
                log.exception("Error reading conciencia.json")
        return cls._nuevo()

    @classmethod
    def _nuevo(cls) -> dict:
        return {
            "estado_general": "ok",
            "nivel_error": 0,
            "procesos": {
                "orquestador": {"estado": "idle"},
                "ejecutor": {"estado": "idle"},
                "reparador": {"estado": "idle"},
            },
            "contexto_global": {
                "ciclo_actual": 0,
                "progreso": "0/0",
                "errores_acumulados": [],
                "arreglos_aplicados": [],
            },
        }

    @classmethod
    def escribir(cls, data: dict) -> None:
        with cls._lock:
            cls.PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = cls.PATH.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
            tmp.replace(cls.PATH)

    @classmethod
    def actualizar_proceso(cls, nombre: str, estado: str) -> None:
        data = cls.leer()
        data["procesos"][nombre] = {
            "estado": estado,
            "ultima_actualizacion": datetime.now(UTC).isoformat(),
        }
        cls.escribir(data)

    @classmethod
    def registrar_error(cls, nivel: int, mensaje: str) -> None:
        data = cls.leer()
        data["nivel_error"] = max(data["nivel_error"], nivel)
        data["contexto_global"]["errores_acumulados"].append(
            {
                "nivel": nivel,
                "mensaje": mensaje,
                "timestamp": datetime.now(UTC).isoformat(),
            },
        )
        if len(data["contexto_global"]["errores_acumulados"]) > 50:
            data["contexto_global"]["errores_acumulados"] = data["contexto_global"]["errores_acumulados"][-50:]
        cls.escribir(data)

    @classmethod
    def nivel_error(cls) -> int:
        return cls.leer().get("nivel_error", 0)
