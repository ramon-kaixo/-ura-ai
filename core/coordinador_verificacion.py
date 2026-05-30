#!/usr/bin/env python3
"""
URA Coordinador de Verificación - Coordina Supervisor y Ejecutor
Define el flujo unificado de verificación y ejecución
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger
from core.tecnico_ejecutor import tecnico_ejecutor
from core.tecnico_supervisor import tecnico_supervisor

logger = get_logger("coordinador_verificacion", log_dir="./logs")


class CoordinadorVerificacion:
    """Coordinador de Verificación - Unifica Supervisor y Ejecutor"""

    def __init__(self):
        """Inicializar coordinador"""
        self.procesos = []

    def procesar_peticion(self, peticion: str, respuesta_ura: str) -> dict[str, Any]:
        """
        Procesar petición unificando Supervisor y Ejecutor

        Flujo:
        1. Técnico Supervisor verifica respuesta
        2. Si aprueba → Ejecuta normalmente
        3. Si rechaza → Técnico Ejecutor con test forzado
        4. Si test forzado tiene éxito → Ejecuta
        5. Si test forzado falla → Soluciones alternativas

        Args:
            peticion: Petición original
            respuesta_ura: Respuesta de URA

        Returns:
            Resultado del proceso
        """
        logger.info(f"Procesando petición: {peticion[:50]}...")

        # Paso 1: Técnico Supervisor verifica respuesta
        logger.info("Paso 1: Técnico Supervisor verificando...")
        resultado_supervisor = tecnico_supervisor.verificar_respuesta(respuesta_ura, peticion)

        if resultado_supervisor["aprobada"]:
            logger.info("Supervisor aprobó, respuesta válida")
            resultado = {
                "peticion": peticion,
                "respuesta_ura": respuesta_ura,
                "supervisor_aprobada": True,
                "ejecutor_ejecutado": False,
                "test_forzado_ejecutado": False,
                "estado": "aprobada_supervisor",
                "ejecutada": True,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
        else:
            logger.warning("Supervisor rechazó, pasando a Ejecutor...")

            # Paso 2: Técnico Ejecutor intenta ejecutar con test forzado
            logger.info("Paso 2: Técnico Ejecutor con test forzado...")
            resultado_ejecutor = tecnico_ejecutor.ejecutar_orden(peticion, respuesta_ura)

            # Verificar si se usó test forzado
            test_forzado_usado = resultado_ejecutor.get("metodo_ejecucion") == "test_forzado"

            if resultado_ejecutor["ejecutada"]:
                logger.info("Ejecutor ejecutó con éxito")
                resultado = {
                    "peticion": peticion,
                    "respuesta_ura": respuesta_ura,
                    "supervisor_aprobada": False,
                    "ejecutor_ejecutado": True,
                    "test_forzado_ejecutado": test_forzado_usado,
                    "test_forzado_resultado": resultado_ejecutor.get("test_forzado"),
                    "estado": "ejecutada_ejecutor",
                    "ejecutada": True,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }
            else:
                logger.warning("Ejecutor no pudo ejecutar")
                resultado = {
                    "peticion": peticion,
                    "respuesta_ura": respuesta_ura,
                    "supervisor_aprobada": False,
                    "ejecutor_ejecutado": True,
                    "test_forzado_ejecutado": test_forzado_usado,
                    "test_forzado_resultado": resultado_ejecutor.get("test_forzado"),
                    "soluciones_alternativas": resultado_ejecutor.get(
                        "soluciones_alternativas", []
                    ),
                    "estado": "no_ejecutada",
                    "ejecutada": False,
                    "timestamp": datetime.now(tz=UTC).isoformat(),
                }

        self.procesos.append(resultado)

        logger.info(f"Proceso completado: {resultado['estado']}")

        return resultado

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        if not self.procesos:
            return {"total": 0}

        aprobadas_supervisor = sum(1 for p in self.procesos if p["supervisor_aprobada"])
        ejecutadas_ejecutor = sum(
            1 for p in self.procesos if p["ejecutor_ejecutado"] and p["ejecutada"]
        )
        test_forzado_exitosos = sum(
            1 for p in self.procesos if p.get("test_forzado_ejecutado") and p["ejecutada"]
        )
        no_ejecutadas = sum(1 for p in self.procesos if not p["ejecutada"])

        return {
            "total_procesos": len(self.procesos),
            "aprobadas_supervisor": aprobadas_supervisor,
            "ejecutadas_ejecutor": ejecutadas_ejecutor,
            "test_forzado_exitosos": test_forzado_exitosos,
            "no_ejecutadas": no_ejecutadas,
            "tasa_aprobacion_supervisor": (
                aprobadas_supervisor / len(self.procesos) if self.procesos else 0
            ),
            "tasa_ejecucion_total": (
                (aprobadas_supervisor + ejecutadas_ejecutor) / len(self.procesos)
                if self.procesos
                else 0
            ),
        }


# Instancia global
coordinador_verificacion = CoordinadorVerificacion()


if __name__ == "__main__":
    coordinador = CoordinadorVerificacion()

    # Test 1: Respuesta aprobada por supervisor
    resultado1 = coordinador.procesar_peticion(
        peticion="¿Cuál es el precio de Bitcoin?", respuesta_ura="Bitcoin está a $50,000"
    )
    print(f"Test 1 - Estado: {resultado1['estado']}")

    # Test 2: Respuesta rechazada pero ejecutada por ejecutor
    resultado2 = coordinador.procesar_peticion(
        peticion="Mira mis correos", respuesta_ura="No puedo acceder a tus correos"
    )
    print(f"Test 2 - Estado: {resultado2['estado']}")

    print(f"Estadísticas: {coordinador.get_estadisticas()}")
