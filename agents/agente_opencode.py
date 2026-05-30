"""Agente OpenCode — integración con OpenCode IDE."""

import logging

log = logging.getLogger(__name__)


class AgenteOpenCode:
    def __init__(self):
        log.info("AgenteOpenCode inicializado")

    def ejecutar_tarea(self, tarea):
        return {"status": "pendiente", "tarea": tarea}

    def get_status(self):
        return {"agente": "opencode", "estado": "operativo"}


agente_opencode = AgenteOpenCode()
