"""Agente Memoria — memoria persistente del sistema URA."""

import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger(__name__)


class AgenteMemoria:
    def __init__(self, path=None):
        self.path = Path(path) if path else Path(__file__).parent.parent / "data" / "memoria.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.memorias = json.loads(self.path.read_text()) if self.path.exists() else []

    def recordar(self, texto, categoria="general"):
        self.memorias.append(
            {"texto": texto, "categoria": categoria, "timestamp": datetime.now().isoformat()}
        )
        self.path.write_text(json.dumps(self.memorias, indent=2, ensure_ascii=False))

    def buscar(self, query, limite=10):
        return [m for m in self.memorias if query.lower() in m["texto"].lower()][:limite]


def get_memoria():
    return AgenteMemoria()


agente_memoria = AgenteMemoria()
