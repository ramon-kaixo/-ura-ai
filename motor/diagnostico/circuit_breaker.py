import logging

log = logging.getLogger("ura.diagnostico.circuit")

class CircuitBreaker:
    FALLOS_MAX = 3
    VENTANA_SEG = 300

    def __init__(self, qdrant):
        self._qdrant = qdrant
        self._fallos = 0
        self._abierto = False

    def operacional(self) -> bool:
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

    def reset(self):
        self._fallos = 0
        self._abierto = False
        log.info("circuit breaker cerrado manualmente")
