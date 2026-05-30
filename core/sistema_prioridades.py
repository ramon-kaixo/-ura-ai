#!/usr/bin/env python3
"""
URA Sistema de Prioridades
Cola de prioridad para peticiones críticas
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger

logger = get_logger("sistema_prioridades", log_dir="./logs")


class SistemaPrioridades:
    """Sistema de Prioridades - Cola de prioridad"""

    def __init__(self):
        """Inicializar sistema de prioridades"""
        self.cola = []
        self.prioridades = {"critica": 1, "alta": 2, "normal": 3, "baja": 4}

    def agregar_peticion(
        self, peticion: str, prioridad: str = "normal", metadata: dict[str, Any] = None
    ) -> str:
        """
        Agregar petición a la cola

        Args:
            peticion: Petición
            prioridad: Prioridad (critica, alta, normal, baja)
            metadata: Metadatos adicionales

        Returns:
            ID de la petición
        """
        if prioridad not in self.prioridades:
            prioridad = "normal"

        peticion_id = f"pet_{datetime.now(tz=UTC).timestamp()}"

        entrada = {
            "id": peticion_id,
            "peticion": peticion,
            "prioridad": prioridad,
            "valor_prioridad": self.prioridades[prioridad],
            "metadata": metadata or {},
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        self.cola.append(entrada)

        # Ordenar por prioridad
        self.cola.sort(key=lambda x: x["valor_prioridad"])

        logger.info(f"Petición agregada: {peticion_id} (prioridad: {prioridad})")

        return peticion_id

    def obtener_siguiente(self) -> Optional[dict[str, Any]]:
        """
        Obtener siguiente petición de la cola

        Returns:
            Siguiente petición o None si está vacía
        """
        if not self.cola:
            return None

        siguiente = self.cola.pop(0)
        logger.info(f"Petición obtenida: {siguiente['id']}")

        return siguiente

    def obtener_peticion_critica(self) -> Optional[dict[str, Any]]:
        """
        Obtener petición crítica (si existe)

        Returns:
            Petición crítica o None
        """
        for i, entrada in enumerate(self.cola):
            if entrada["prioridad"] == "critica":
                self.cola.pop(i)
                logger.info(f"Petición crítica obtenida: {entrada['id']}")
                return entrada

        return None

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        if not self.cola:
            return {"total": 0}

        por_prioridad = {}
        for entrada in self.cola:
            prioridad = entrada["prioridad"]
            por_prioridad[prioridad] = por_prioridad.get(prioridad, 0) + 1

        return {"total_peticiones": len(self.cola), "por_prioridad": por_prioridad}


# Instancia global
sistema_prioridades = SistemaPrioridades()


if __name__ == "__main__":
    prioridades = SistemaPrioridades()

    # Test
    prioridades.agregar_peticion("Petición normal", "normal")
    prioridades.agregar_peticion("Petición crítica", "critica")
    prioridades.agregar_peticion("Petición alta", "alta")

    siguiente = prioridades.obtener_siguiente()
    print(f"Siguiente: {siguiente}")

    critica = prioridades.obtener_peticion_critica()
    print(f"Crítica: {critica}")

    print(f"Estadísticas: {prioridades.get_estadisticas()}")
