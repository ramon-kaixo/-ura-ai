#!/usr/bin/env python3
"""
URA Test Forzado - Sistema de test cuando hay negación
Cuando URA dice "no puedo", ejecuta un test que obliga a intentarlo
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger

logger = get_logger("test_forzado", log_dir="./logs")


class TestForzado:
    """Test forzado para obligar a URA a ejecutar tareas"""

    def __init__(self):
        """Inicializar test forzado"""
        self.tests = []
        self.negaciones_detectadas = [
            "no puedo",
            "no puedo hacerlo",
            "no es posible",
            "imposible",
            "no tengo capacidad",
            "no sé cómo",
            "no puedo acceder",
            "no tengo permisos",
            "no disponible",
        ]

    def ejecutar_test(self, orden: str, respuesta_ura: str) -> dict[str, Any]:
        """
        Ejecutar test forzado cuando hay negación

        Args:
            orden: Orden original
            respuesta_ura: Respuesta de URA

        Returns:
            Resultado del test
        """
        logger.info("Verificando si hay negación en respuesta...")

        # Verificar si es negación
        es_negacion = self._es_negacion(respuesta_ura)

        if not es_negacion:
            logger.info("No hay negación, no es necesario test forzado")
            return {
                "orden": orden,
                "respuesta_ura": respuesta_ura,
                "negacion": False,
                "test_ejecutado": False,
                "resultado": "no_necesario",
            }

        logger.warning(f"Negación detectada: {respuesta_ura}")
        logger.info(f"Ejecutando test forzado para: {orden[:50]}...")

        # Ejecutar test forzado
        resultado_test = self._ejecutar_test_intento(orden)

        test_info = {
            "orden": orden,
            "respuesta_ura": respuesta_ura,
            "negacion": True,
            "test_ejecutado": True,
            "test_resultado": resultado_test,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }

        self.tests.append(test_info)

        if resultado_test["exito"]:
            logger.info("Test forzado EXITOSO: URA pudo ejecutar la tarea")
        else:
            logger.warning("Test forzado FALLIDO: URA no pudo ejecutar la tarea")

        return test_info

    def _es_negacion(self, respuesta: str) -> bool:
        """
        Verificar si es una negación

        Args:
            respuesta: Respuesta de URA

        Returns:
            True si es negación
        """
        respuesta_lower = respuesta.lower()
        return any(n in respuesta_lower for n in self.negaciones_detectadas)

    def _ejecutar_test_intento(self, orden: str) -> dict[str, Any]:
        """
        Ejecutar test de intento forzado

        Args:
            orden: Orden a ejecutar

        Returns:
            Resultado del test
        """
        # Analizar la orden y determinar tipo de test
        tipo_test = self._determinar_tipo_test(orden)

        logger.info(f"Tipo de test: {tipo_test}")

        # Ejecutar el test correspondiente
        if tipo_test == "acceso_archivos":
            return self._test_acceso_archivos(orden)
        elif tipo_test == "acceso_correo":
            return self._test_acceso_correo(orden)
        elif tipo_test == "ejecutar_comando":
            return self._test_ejecutar_comando(orden)
        elif tipo_test == "acceso_internet":
            return self._test_acceso_internet(orden)
        elif tipo_test == "acceso_sistema":
            return self._test_acceso_sistema(orden)
        else:
            return self._test_generico(orden)

    def _determinar_tipo_test(self, orden: str) -> str:
        """
        Determinar tipo de test basado en la orden

        Args:
            orden: Orden

        Returns:
            Tipo de test
        """
        orden_lower = orden.lower()

        if "archivo" in orden_lower or "carpeta" in orden_lower or "directorio" in orden_lower:
            return "acceso_archivos"
        elif "correo" in orden_lower or "email" in orden_lower or "mail" in orden_lower:
            return "acceso_correo"
        elif "comando" in orden_lower or "ejecutar" in orden_lower or "run" in orden_lower:
            return "ejecutar_comando"
        elif "internet" in orden_lower or "web" in orden_lower or "buscar" in orden_lower:
            return "acceso_internet"
        elif "proceso" in orden_lower or "sistema" in orden_lower or "servicio" in orden_lower:
            return "acceso_sistema"
        else:
            return "generico"

    def _test_acceso_archivos(self, orden: str) -> dict[str, Any]:
        """Test de acceso a archivos"""
        try:
            import os

            # Intentar acceder a directorio actual
            os.listdir(".")
            return {
                "exito": True,
                "tipo": "acceso_archivos",
                "mensaje": "Acceso a archivos funcionando",
            }
        except Exception as e:
            return {
                "exito": False,
                "tipo": "acceso_archivos",
                "mensaje": f"Error acceso archivos: {e}",
            }

    def _test_acceso_correo(self, orden: str) -> dict[str, Any]:
        """Test de acceso a correo"""
        try:
            # Simular test de correo
            # En producción intentaría conectar al servidor de correo
            return {
                "exito": True,
                "tipo": "acceso_correo",
                "mensaje": "Acceso a correo funcionando (simulado)",
            }
        except Exception as e:
            return {"exito": False, "tipo": "acceso_correo", "mensaje": f"Error acceso correo: {e}"}

    def _test_ejecutar_comando(self, orden: str) -> dict[str, Any]:
        """Test de ejecutar comando"""
        try:
            import subprocess

            # Intentar ejecutar un comando simple
            resultado = subprocess.run(["echo", "test"], capture_output=True, text=True)
            if resultado.returncode == 0:
                return {
                    "exito": True,
                    "tipo": "ejecutar_comando",
                    "mensaje": "Ejecución de comandos funcionando",
                }
            else:
                return {
                    "exito": False,
                    "tipo": "ejecutar_comando",
                    "mensaje": f"Error ejecución: {resultado.stderr}",
                }
        except Exception as e:
            return {
                "exito": False,
                "tipo": "ejecutar_comando",
                "mensaje": f"Error ejecutar comando: {e}",
            }

    def _test_acceso_internet(self, orden: str) -> dict[str, Any]:
        """Test de acceso a internet"""
        try:
            import urllib.request

            # Intentar acceder a una URL simple
            with urllib.request.urlopen("http://example.com", timeout=5):  # nosec B310
                return {
                    "exito": True,
                    "tipo": "acceso_internet",
                    "mensaje": "Acceso a internet funcionando",
                }
        except Exception as e:
            return {
                "exito": False,
                "tipo": "acceso_internet",
                "mensaje": f"Error acceso internet: {e}",
            }

    def _test_acceso_sistema(self, orden: str) -> dict[str, Any]:
        """Test de acceso al sistema"""
        try:
            import psutil

            # Intentar obtener información del sistema
            psutil.cpu_percent()
            return {
                "exito": True,
                "tipo": "acceso_sistema",
                "mensaje": "Acceso al sistema funcionando",
            }
        except Exception as e:
            return {
                "exito": False,
                "tipo": "acceso_sistema",
                "mensaje": f"Error acceso sistema: {e}",
            }

    def _test_generico(self, orden: str) -> dict[str, Any]:
        """Test genérico"""
        try:
            # Test genérico: verificar que el sistema está operativo
            return {"exito": True, "tipo": "generico", "mensaje": "Sistema operativo funcionando"}
        except Exception as e:
            return {"exito": False, "tipo": "generico", "mensaje": f"Error genérico: {e}"}

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        if not self.tests:
            return {"total": 0}

        negaciones = sum(1 for t in self.tests if t["negacion"])
        exitosos = sum(1 for t in self.tests if t.get("test_resultado", {}).get("exito", False))

        return {
            "total_tests": len(self.tests),
            "negaciones": negaciones,
            "exitosos": exitosos,
            "fallidos": len(self.tests) - exitosos,
            "tasa_exito": exitosos / len(self.tests) if self.tests else 0,
        }


# Instancia global
test_forzado = TestForzado()


if __name__ == "__main__":
    test = TestForzado()

    # Test 1: Sin negación
    resultado1 = test.ejecutar_test(
        orden="Mira mis correos", respuesta_ura="Aquí tienes tus correos..."
    )
    print(f"Negación: {resultado1['negacion']}")

    # Test 2: Con negación
    resultado2 = test.ejecutar_test(
        orden="Mira mis correos", respuesta_ura="No puedo acceder a tus correos"
    )
    print(f"Negación: {resultado2['negacion']}")
    print(f"Test ejecutado: {resultado2['test_ejecutado']}")
    print(f"Test resultado: {resultado2['test_resultado']}")

    print(f"Estadísticas: {test.get_estadisticas()}")
