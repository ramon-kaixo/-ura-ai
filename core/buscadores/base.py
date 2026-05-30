"""Stub: BaseSearchAgent — clase base para agentes buscadores."""

import logging
from datetime import datetime

log = logging.getLogger(__name__)


class SearchAgentMeta(type):
    """Metaclass para registrar agentes buscadores automáticamente."""

    registry = {}

    def __new__(mcs, name, bases, namespace):
        cls = super().__new__(mcs, name, bases, namespace)
        if name != "BaseSearchAgent":
            mcs.registry[name] = cls
        return cls


class BaseSearchAgent(metaclass=SearchAgentMeta):
    """Clase base para todos los agentes de búsqueda."""

    nombre: str = "base"
    intervalo_horas: int = 24

    def __init__(self):
        self.ultima_ejecucion = None
        log.info("SearchAgent %s inicializado", self.nombre)

    def buscar(self, query: str = None) -> list:
        raise NotImplementedError

    def ejecutar(self) -> dict:
        resultados = self.buscar()
        self.ultima_ejecucion = datetime.now()
        return {"agente": self.nombre, "resultados": len(resultados), "datos": resultados}
