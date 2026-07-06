import logging
from collections import deque
from typing import Any

log = logging.getLogger("ura.scanner.sliding")


class SlidingWindow:
    """Ventana deslizante para detección de flapping en servicios."""

    def __init__(self, maxlen: int = 3):
        self._buffer = deque(maxlen=maxlen)

    def add_and_check(self, estado: Any) -> list:
        """Añade un estado y detecta flapping entre las últimas N muestras."""
        self._buffer.append(estado)
        return self._detectar_flapping()

    def _detectar_flapping(self) -> list:
        """Detecta servicios que cambian de estado entre muestras."""
        if len(self._buffer) < 3:
            return []
        flapping = []
        servicios = [s.servicios for s in self._buffer if hasattr(s, "servicios")]
        for svc in set().union(*(s.keys() for s in servicios)):
            estados = [s.get(svc) for s in servicios if svc in s]
            if len(estados) >= 3:
                unicos = set(estados)
                if len(unicos) > 1:
                    flapping.append({"servicio": svc, "cambios": list(unicos), "conteo": len(estados)})
        return flapping
