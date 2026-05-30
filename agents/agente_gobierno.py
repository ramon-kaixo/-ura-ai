"""Agente Gobierno — obligaciones gubernamentales y fiscales."""

import logging

log = logging.getLogger(__name__)


class AgenteGobierno:
    def __init__(self):
        log.info("AgenteGobierno inicializado")

    def get_obligaciones_pendientes(self):
        return []

    def verificar_plazos(self):
        return {"pendientes": 0, "proximas": []}


agente_gobierno = AgenteGobierno()
