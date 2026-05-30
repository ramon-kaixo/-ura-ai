#!/usr/bin/env python3
"""
Agente Cocina (Chef I+D) - Generador de recetas basado en tendencias
"""

import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AgenteCocina:
    """Agente de cocina que genera propuestas de recetas"""

    def __init__(self, output_dir: Path = None):
        self.output_dir = output_dir or Path.home() / ".ura" / "output"
        self.log_path = Path(__file__).parent.parent / "LOG_ACTIVIDAD_URA.md"
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _log_actividad(self, accion: str):
        """Escribir línea en bitácora"""
        try:
            timestamp = datetime.now().strftime("%H:%M")
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(f"{timestamp} - [COCINA] - {accion}\n")
        except Exception as e:
            logger.error(f"Error escribiendo en bitácora: {e}")

    def generar_recetas(self, menu_semanal: list = None) -> dict:
        """Generar 2 propuestas de recetas por menú semanal"""
        try:
            # Si no hay menú, usar menú por defecto
            if not menu_semanal:
                menu_semanal = [
                    "Lunes: Menú del día",
                    "Martes: Menú del día",
                    "Miércoles: Menú del día",
                    "Jueves: Menú del día",
                    "Viernes: Menú del día",
                    "Sábado: Menú del día",
                    "Domingo: Menú del día",
                ]

            propuestas = []

            # Generar 2 propuestas por día
            for dia_menu in menu_semanal:
                dia = dia_menu.split(":")[0]
                propuesta_1 = {
                    "dia": dia,
                    "titulo": f"Propuesta 1 - {dia}",
                    "ingredientes": ["Ingrediente 1", "Ingrediente 2", "Ingrediente 3"],
                    "preparacion": "Paso 1, Paso 2, Paso 3",
                    "origen": "SYNTHETIC",
                }
                propuesta_2 = {
                    "dia": dia,
                    "titulo": f"Propuesta 2 - {dia}",
                    "ingredientes": ["Ingrediente A", "Ingrediente B", "Ingrediente C"],
                    "preparacion": "Paso A, Paso B, Paso C",
                    "origen": "SYNTHETIC",
                }
                propuestas.extend([propuesta_1, propuesta_2])

            resultado = {
                "menu_semanal": menu_semanal,
                "propuestas": propuestas,
                "timestamp": datetime.now().isoformat(),
                "origin": "SYNTHETIC",
            }

            # Guardar en JSON
            output_path = self.output_dir / "recetas_sugeridas.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(resultado, f, indent=2, ensure_ascii=False)

            self._log_actividad(f"Generadas {len(propuestas)} propuestas de recetas")
            logger.info(f"Recetas guardadas en {output_path}")

            return resultado

        except Exception as e:
            logger.error(f"Error generando recetas: {e}")
            raise


def main():
    """Función principal para ejecutar el agente"""
    logging.basicConfig(level=logging.INFO)
    agente = AgenteCocina()
    agente.generar_recetas()


if __name__ == "__main__":
    main()
