#!/usr/bin/env python3
"""
URA Scheduler de Buscadores - Integración con agente_scheduler
Configura ejecución periódica de todos los buscadores
"""

from datetime import datetime, UTC
from typing import Any

from core.logging_config import get_logger

# Optional dependencies — gracefully degrade if absent.
try:
    from core.lock_manager import lock_manager  # type: ignore
except ImportError:
    lock_manager = None  # type: ignore

try:
    from core.database import db_manager  # type: ignore
except ImportError:
    db_manager = None  # type: ignore

from core.buscadores.buscador_aplicaciones import buscador_aplicaciones
from core.buscadores.buscador_documentacion import buscador_documentacion
from core.buscadores.buscador_estudios import buscador_estudios
from core.buscadores.buscador_manuales import buscador_manuales
from core.buscadores.buscador_noticias import buscador_noticias
from core.buscadores.buscador_tendencias import buscador_tendencias

logger = get_logger("scheduler_buscadores", log_dir="./logs")


class SchedulerBuscadores:
    """Scheduler de Buscadores - Ejecución periódica"""

    def __init__(self):
        """Inicializar scheduler"""
        self.tareas = {
            "buscador_noticias": {"intervalo": "1h", "funcion": self._ejecutar_noticias},
            "buscador_estudios": {"intervalo": "1d", "funcion": self._ejecutar_estudios},
            "buscador_aplicaciones": {"intervalo": "1sem", "funcion": self._ejecutar_aplicaciones},
            "buscador_manuales": {"intervalo": "manual", "funcion": self._ejecutar_manuales},
            "buscador_tendencias": {"intervalo": "6h", "funcion": self._ejecutar_tendencias},
            "buscador_documentacion": {
                "intervalo": "1sem",
                "funcion": self._ejecutar_documentacion,
            },
        }

    def ejecutar_tarea(self, nombre_tarea: str) -> dict[str, Any]:
        """
        Ejecutar tarea específica con lock

        Args:
            nombre_tarea: Nombre de la tarea

        Returns:
            Resultado de la ejecución
        """
        logger.info(f"Ejecutando tarea: {nombre_tarea}")

        # Adquirir lock (si la capa está disponible)
        lock = None
        if lock_manager is not None:
            lock = lock_manager.adquirir_lock(nombre_tarea, timeout=3600)
            if not lock:
                logger.warning(f"Tarea {nombre_tarea} ya en ejecución")
                return {"estado": "bloqueado", "tarea": nombre_tarea}

        try:
            # Ejecutar tarea
            tarea = self.tareas.get(nombre_tarea)
            if not tarea:
                logger.error(f"Tarea no encontrada: {nombre_tarea}")
                return {"estado": "error", "mensaje": "Tarea no encontrada"}

            resultado = tarea["funcion"]()

            # Guardar en base de datos (si la capa está disponible)
            if db_manager is not None:
                db_manager.save_resultado_buscador(
                    tipo=nombre_tarea,
                    categoria="general",
                    resultados=resultado,
                    cantidad=len(resultado) if isinstance(resultado, list) else 1,
                )
            else:
                logger.debug(
                    "db_manager no disponible — resultado de %s no persistido", nombre_tarea
                )

            logger.info(
                f"Tarea {nombre_tarea} completada: {len(resultado) if isinstance(resultado, list) else 1} resultados"
            )

            return {
                "estado": "completado",
                "tarea": nombre_tarea,
                "resultados": len(resultado) if isinstance(resultado, list) else 1,
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"Error ejecutando tarea {nombre_tarea}: {e}")
            return {"estado": "error", "mensaje": str(e)}

        finally:
            # Liberar lock (si está disponible)
            if lock_manager is not None and lock is not None:
                lock_manager.liberar_lock(lock)

    def ejecutar_todas(self) -> dict[str, Any]:
        """
        Ejecutar todas las tareas

        Returns:
            Resultados de todas las tareas
        """
        logger.info("Ejecutando todas las tareas...")

        resultados = {}

        for nombre_tarea in self.tareas:
            resultado = self.ejecutar_tarea(nombre_tarea)
            resultados[nombre_tarea] = resultado

        logger.info(
            f"Todas las tareas completadas: {len([r for r in resultados.values() if r['estado'] == 'completado'])}/{len(resultados)}"
        )

        return resultados

    def _ejecutar_noticias(self):
        """Ejecutar buscador de noticias"""
        return buscador_noticias.buscar_noticias()

    def _ejecutar_estudios(self):
        """Ejecutar buscador de estudios"""
        return buscador_estudios.buscar_estudios()

    def _ejecutar_aplicaciones(self):
        """Ejecutar buscador de aplicaciones"""
        return buscador_aplicaciones.buscar_aplicaciones()

    def _ejecutar_manuales(self):
        """Ejecutar buscador de manuales"""
        return buscador_manuales.descargar_manuales()

    def _ejecutar_tendencias(self):
        """Ejecutar buscador de tendencias"""
        return buscador_tendencias.analizar_tendencias()

    def _ejecutar_documentacion(self):
        """Ejecutar buscador de documentación"""
        resultados = []
        for tema in ["DeepSeek API", "Gemini API", "Claude API", "Mistral API"]:
            resultado = buscador_documentacion.buscar_documentacion(tema, "ias")
            resultados.extend(resultado)
        return resultados

    def get_configuracion(self) -> dict[str, Any]:
        """Obtener configuración de tareas"""
        return {nombre: {"intervalo": tarea["intervalo"]} for nombre, tarea in self.tareas.items()}


# Instancia global
scheduler_buscadores = SchedulerBuscadores()


if __name__ == "__main__":
    scheduler = SchedulerBuscadores()

    # Test: ejecutar una tarea específica
    resultado = scheduler.ejecutar_tarea("buscador_noticias")
    print(f"Resultado: {resultado}")

    # Test: obtener configuración
    config = scheduler.get_configuracion()
    print(f"Configuración: {config}")
