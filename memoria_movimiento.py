"""memoria_movimiento.py — URA / Memoria 3 (movimiento / cubos)"""

from __future__ import annotations
import time
from dataclasses import dataclass

TIEMPO_MAX = 30.0


@dataclass
class Cubo:
    id_cubo: str
    nodo_destino: str
    momento_salida: float
    volvio: bool = False
    momento_vuelta: float | None = None


class MemoriaMovimiento:
    def __init__(self, nombre_nodo: str, tiempo_max_s: float = TIEMPO_MAX) -> None:
        self.nombre_nodo = nombre_nodo
        self._tiempo_max = tiempo_max_s
        self._cubos: dict[str, Cubo] = {}
        self._reloj = time.monotonic

    def mandar_cubo(self, id_cubo: str, nodo_destino: str) -> Cubo:
        c = Cubo(id_cubo=id_cubo, nodo_destino=nodo_destino, momento_salida=self._reloj())
        self._cubos[id_cubo] = c
        return c

    def cubo_volvio(self, id_cubo: str) -> bool:
        c = self._cubos.get(id_cubo)
        if c is None:
            return False
        c.volvio = True
        c.momento_vuelta = self._reloj()
        del self._cubos[id_cubo]
        return True

    def cubos_sin_volver(self) -> list[Cubo]:
        ahora = self._reloj()
        return [c for c in self._cubos.values() if ahora - c.momento_salida > self._tiempo_max]

    def circulo_sano(self) -> bool:
        return len(self.cubos_sin_volver()) == 0

    def nodos_atascados(self) -> list[str]:
        return [c.nodo_destino for c in self.cubos_sin_volver()]

    def resumen(self) -> dict:
        rotos = self.cubos_sin_volver()
        return {
            "nodo": self.nombre_nodo,
            "en_viaje": len(self._cubos),
            "sano": len(rotos) == 0,
            "atascados": [c.id_cubo for c in rotos],
            "nodos": [c.nodo_destino for c in rotos],
        }
