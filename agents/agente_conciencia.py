"""Agente Conciencia — autoconocimiento del sistema URA."""

import logging
from datetime import datetime

log = logging.getLogger(__name__)


class AgenteConciencia:
    def __init__(self):
        self.estado = "operativo"
        self.inicio = datetime.now()

    def get_estado(self):
        return {
            "agente": "conciencia",
            "estado": self.estado,
            "uptime": str(datetime.now() - self.inicio),
        }

    def introspect(self):
        return f"URA operativo desde {self.inicio.isoformat()}"


agente_conciencia = AgenteConciencia()
