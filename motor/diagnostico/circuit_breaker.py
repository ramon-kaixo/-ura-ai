import logging

log = logging.getLogger("ura.diagnostico.circuit")

class CircuitBreaker:
    """Circuit breaker para Qdrant: abre tras N fallos consecutivos."""

    FALLOS_MAX = 3
    VENTANA_SEG = 300

    def __init__(self, qdrant) -> None:
        self._qdrant = qdrant
        self._fallos = 0
        self._abierto = False

    def operacional(self) -> bool:
        """Devuelve True si Qdrant responde; abre el circuito tras FALLOS_MAX fallos."""
        if self._abierto:
            return False
        ok = self._qdrant.health()
        if ok:
            self._fallos = 0
        else:
            self._fallos += 1
            if self._fallos >= self.FALLOS_MAX:
                self._abierto = True
                log.warning("circuit breaker abierto tras %d fallos", self._fallos)
        return ok

    def reset(self) -> None:
        """Cierra el circuit breaker manualmente."""
        self._fallos = 0
        self._abierto = False
        log.info("circuit breaker cerrado manualmente")
