"""memoria_fallos.py — URA / Memoria 2 (fallos y arreglos)"""

from __future__ import annotations
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

MAX_FALLOS = 5
UMBRAL_PATRON = 3


@dataclass
class Fallo:
    tipo: str
    mensaje: str
    arreglo: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(tz=timezone.utc).isoformat())


class MemoriaFallos:
    def __init__(self, nombre_pieza: str, max_fallos: int = MAX_FALLOS, umbral_patron: int = UMBRAL_PATRON) -> None:
        self.nombre_pieza = nombre_pieza
        self._fallos: deque[Fallo] = deque(maxlen=max_fallos)
        self._arreglos: dict[str, str] = {}
        self._umbral = umbral_patron

    def registrar(self, tipo: str, mensaje: str, arreglo: str | None = None) -> Fallo:
        f = Fallo(tipo=tipo, mensaje=mensaje, arreglo=arreglo)
        self._fallos.append(f)
        if arreglo:
            self._arreglos[tipo] = arreglo
        return f

    def contar(self, tipo: str) -> int:
        return sum(1 for f in self._fallos if f.tipo == tipo)

    def es_patron(self, tipo: str) -> bool:
        return self.contar(tipo) >= self._umbral

    def arreglo_conocido(self, tipo: str) -> str | None:
        return self._arreglos.get(tipo)

    def fallos_recientes(self) -> list[Fallo]:
        return list(self._fallos)

    def hay_patron_activo(self) -> str | None:
        vistos: set[str] = set()
        for f in self._fallos:
            if f.tipo in vistos:
                continue
            vistos.add(f.tipo)
            if self.es_patron(f.tipo):
                return f.tipo
        return None

    def resumen(self) -> dict:
        tipos: dict[str, int] = {}
        for f in self._fallos:
            tipos[f.tipo] = tipos.get(f.tipo, 0) + 1
        return {
            "pieza": self.nombre_pieza,
            "n_fallos": len(self._fallos),
            "tipos": tipos,
            "patron": self.hay_patron_activo(),
            "arreglos": list(self._arreglos.keys()),
        }
