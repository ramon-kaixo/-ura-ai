#!/usr/bin/env python3
"""
URA Técnico Ejecutor - Ejecución hacia abajo
Obliga a URA a ejecutar órdenes, busca soluciones alternativas
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger
from core.test_forzado import test_forzado

logger = get_logger("tecnico_ejecutor", log_dir="./logs")


class TecnicoEjecutor:
    """Técnico Ejecutor - Obliga a ejecutar órdenes"""

    def __init__(self):
        """Inicializar técnico ejecutor"""
        self.ordenes = []
        self.soluciones_alternativas = []

    def ejecutar_orden(self, orden: str, ura_response: str = None) -> dict[str, Any]:
        """
        Ejecutar orden obligando a URA

        Args:
            orden: Orden a ejecutar
            ura_response: Respuesta de URA (si ya respondió)

        Returns:
            Resultado de ejecución
        """
        logger.info(f"Ejecutando orden: {orden[:50]}...")

        # Verificar si URA respondió
        if ura_response:
            if self._es_rechazo(ura_response):
                logger.warning(f"URA rechazó: {ura_response}")

                # Ejecutar test forzado
                logger.info("Ejecutando test forzado...")
                test_resultado = test_forzado.ejecutar_test(orden, ura_response)

                # Si el test forzado tiene éxito, marcar como ejecutada
                if test_resultado.get("test_resultado", {}).get("exito", False):
                    logger.info("Test forzado exitoso, orden marcada como ejecutada")
                    resultado = {
                        "orden": orden,
                        "ura_response": ura_response,
                        "rechazo": True,
                        "test_forzado": test_resultado,
                        "soluciones_alternativas": [],
                        "ejecutada": True,
                        "metodo_ejecucion": "test_forzado",
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
                else:
                    # Si el test falla, buscar soluciones alternativas
                    logger.warning("Test forzado falló, buscando soluciones alternativas...")
                    soluciones = self._buscar_soluciones_alternativas(orden)

                    resultado = {
                        "orden": orden,
                        "ura_response": ura_response,
                        "rechazo": True,
                        "test_forzado": test_resultado,
                        "soluciones_alternativas": soluciones,
                        "ejecutada": False,
                        "metodo_ejecucion": "soluciones_alternativas",
                        "timestamp": datetime.now(tz=UTC).isoformat(),
                    }
            else:
                resultado = {
                    "orden": orden,
                    "ura_response": ura_response,
                    "rechazo": False,
                    "ejecutada": True,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
        else:
            # URA no ha respondido, obligar a ejecutar
            resultado = {
                "orden": orden,
                "ura_response": None,
                "rechazo": False,
                "ejecutada": True,  # Se ejecutará
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        self.ordenes.append(resultado)

        if resultado["ejecutada"]:
            logger.info("Orden EJECUTADA")
        else:
            logger.warning(f"Orden NO EJECUTADA (se buscaron {len(soluciones)} alternativas)")

        return resultado

    def _es_rechazo(self, response: str) -> bool:
        """
        Verificar si es un rechazo

        Args:
            response: Respuesta de URA

        Returns:
            True si es rechazo
        """
        rechazos = [
            "no puedo",
            "no puedo hacerlo",
            "no es posible",
            "imposible",
            "no tengo capacidad",
            "no sé cómo",
            "no puedo acceder",
        ]

        response_lower = response.lower()
        return any(r in response_lower for r in rechazos)

    def _buscar_soluciones_alternativas(self, orden: str) -> list[dict[str, str]]:
        """
        Buscar soluciones alternativas

        Args:
            orden: Orden original

        Returns:
            Lista de soluciones alternativas
        """
        logger.info(f"Buscando soluciones alternativas para: {orden[:50]}...")

        soluciones = []

        # Solución 1: Usar herramientas del sistema
        soluciones.append(
            {
                "solucion": "Usar herramientas del sistema",
                "comando": self._generar_comando_herramientas(orden),
            }
        )

        # Solución 2: Consultar documentación
        soluciones.append(
            {"solucion": "Consultar documentación", "accion": "Buscar en biblioteca/manuales"}
        )

        # Solución 3: Usar agentes especializados
        soluciones.append(
            {
                "solucion": "Usar agentes especializados",
                "agente": self._determinar_agente_especializado(orden),
            }
        )

        # Solución 4: Consultar internet
        soluciones.append({"solucion": "Consultar internet", "busqueda": orden})

        # Solución 5: Usar scripts existentes
        soluciones.append(
            {
                "solucion": "Usar scripts existentes",
                "script": self._buscar_script_relacionado(orden),
            }
        )

        self.soluciones_alternativas.extend(soluciones)

        return soluciones

    def _generar_comando_herramientas(self, orden: str) -> str:
        """Generar comando usando herramientas del sistema"""
        # Analizar orden y generar comando
        if "correos" in orden.lower():
            return "agente_email --listar --recientes"
        elif "archivos" in orden.lower():
            return "bibliotecario_pasillo --buscar"
        elif "procesos" in orden.lower():
            return "agente_sistemas --listar_procesos"
        else:
            return f"generic_tool --orden '{orden}'"

    def _determinar_agente_especializado(self, orden: str) -> str:
        """Determinar agente especializado para la orden"""
        orden_lower = orden.lower()

        if "correo" in orden_lower or "email" in orden_lower:
            return "agente_email"
        elif "documento" in orden_lower or "carta" in orden_lower:
            return "agente_documentos"
        elif "video" in orden_lower or "foto" in orden_lower:
            return "agente_multimedia"
        elif "programar" in orden_lower or "código" in orden_lower:
            return "agente_programador"
        else:
            return "agente_universal"

    def _buscar_script_relacionado(self, orden: str) -> str:
        """Buscar script relacionado con la orden"""
        # Buscar en scripts/ directorio
        orden_lower = orden.lower()

        if "limpiar" in orden_lower:
            return "scripts/auto_cleaner.py"
        elif "reparar" in orden_lower:
            return "scripts/repair_all.py"
        elif "backup" in orden_lower:
            return "scripts/backup.py"
        else:
            return "scripts/generic.py"

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        if not self.ordenes:
            return {"total": 0}

        ejecutadas = sum(1 for o in self.ordenes if o["ejecutada"])
        rechazadas = sum(1 for o in self.ordenes if o["rechazo"])

        return {
            "total": len(self.ordenes),
            "ejecutadas": ejecutadas,
            "rechazadas": rechazadas,
            "tasa_ejecucion": ejecutadas / len(self.ordenes),
            "soluciones_alternativas": len(self.soluciones_alternativas),
        }


# Instancia global
tecnico_ejecutor = TecnicoEjecutor()


if __name__ == "__main__":
    ejecutor = TecnicoEjecutor()

    # Test 1: Orden ejecutada
    resultado1 = ejecutor.ejecutar_orden(
        orden="Mira mis correos", ura_response="Aquí tienes tus correos..."
    )
    print(f"Ejecutada: {resultado1['ejecutada']}")

    # Test 2: Orden rechazada
    resultado2 = ejecutor.ejecutar_orden(
        orden="Mira mis correos", ura_response="No puedo acceder a tus correos"
    )
    print(f"Ejecutada: {resultado2['ejecutada']}")
    print(f"Soluciones alternativas: {len(resultado2['soluciones_alternativas'])}")

    print(f"Estadísticas: {ejecutor.get_estadisticas()}")
