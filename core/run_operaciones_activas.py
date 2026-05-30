#!/usr/bin/env python3
"""
URA Operaciones Activas - Ejecución automática de agentes
Ejecuta agente_cocina.py, agente_creativo.py y genera datos sintéticos
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class OperacionesActivas:
    """Coordinador de operaciones activas"""

    def __init__(self):
        self.agents_dir = Path(__file__).parent / "agents"
        self.output_dir = Path.home() / ".ura" / "output"
        self.synthetic_dir = Path.home() / ".ura" / "synthetic"
        self.log_path = Path(__file__).parent / "LOG_ACTIVIDAD_URA.md"

    def _log_actividad(self, agente: str, accion: str):
        """Escribir línea en bitácora"""
        try:
            timestamp = datetime.now().strftime("%H:%M")
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} - [{agente}] - {accion}\n")
        except Exception as e:
            logger.error(f"Error escribiendo en bitácora: {e}")

    def ejecutar_agente_cocina(self):
        """Ejecutar agente de cocina"""
        try:
            from core.agents.agente_cocina import AgenteCocina

            agente = AgenteCocina(self.output_dir)
            resultado = agente.generar_recetas()
            self._log_actividad("COCINA", "Recetas generadas exitosamente")
            return resultado
        except Exception as e:
            logger.error(f"Error ejecutando agente cocina: {e}")
            self._log_actividad("COCINA", f"Error: {str(e)}")
            return None

    def ejecutar_agente_creativo(self):
        """Ejecutar agente creativo"""
        try:
            from core.agents.agente_creativo import AgenteCreativo

            agente = AgenteCreativo(self.output_dir)
            resultado = agente.generar_marketing()
            self._log_actividad("CREATIVO", "Marketing generado exitosamente")
            return resultado
        except Exception as e:
            logger.error(f"Error ejecutando agente creativo: {e}")
            self._log_actividad("CREATIVO", f"Error: {str(e)}")
            return None

    def verificar_datos_sinteticos(self):
        """Verificar que los datos sintéticos existan"""
        archivos_requeridos = [
            "SYN_flujo_gente.json",
            "SYN_competencia.json",
            "SYN_horarios_pico.json",
        ]

        estado = {}
        for archivo in archivos_requeridos:
            ruta = self.synthetic_dir / archivo
            estado[archivo] = ruta.exists()

        return estado

    def ejecutar_todo(self):
        """Ejecutar todas las operaciones activas"""
        logger.info("Iniciando operaciones activas")
        self._log_actividad("SISTEMA", "Iniciando ciclo de operaciones activas")

        # Ejecutar agentes
        resultado_cocina = self.ejecutar_agente_cocina()
        resultado_creativo = self.ejecutar_agente_creativo()

        # Verificar datos sintéticos
        estado_sinteticos = self.verificar_datos_sinteticos()

        resultado = {
            "timestamp": datetime.now().isoformat(),
            "agente_cocina": resultado_cocina is not None,
            "agente_creativo": resultado_creativo is not None,
            "datos_sinteticos": estado_sinteticos,
        }

        self._log_actividad("SISTEMA", f"Ciclo completado: {resultado}")
        logger.info(f"Operaciones activas completadas: {resultado}")

        return resultado


def main():
    """Función principal"""
    logging.basicConfig(level=logging.INFO)
    operaciones = OperacionesActivas()
    resultado = operaciones.ejecutar_todo()
    print(json.dumps(resultado, indent=2))


if __name__ == "__main__":
    main()
