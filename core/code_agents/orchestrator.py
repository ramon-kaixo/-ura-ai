#!/usr/bin/env python3
"""
Orquestador de Agentes de Código - URA App
Coordina creadores, revisores y herramientas automáticas
"""

import json
import logging
import shutil
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CodeAgentsOrchestrator:
    """Orquestador principal de agentes de código"""

    def __init__(self):
        self.ura_app_path = Path("/Users/ramonesnaola/URA/ura_ia_1972")
        self.code_agents_path = self.ura_app_path / "core" / "code_agents"
        self.active_path = self.code_agents_path / "active"
        self.inactive_path = self.code_agents_path / "inactive"
        self.history_path = self.code_agents_path / "history"
        self.generators_path = self.code_agents_path / "generators"
        self.reviewers_path = self.code_agents_path / "reviewers"
        self.tools_path = self.code_agents_path / "tools"
        self.registry_file = self.code_agents_path / "registry.json"

        # Crear directorios
        self.active_path.mkdir(parents=True, exist_ok=True)
        self.inactive_path.mkdir(parents=True, exist_ok=True)
        self.history_path.mkdir(parents=True, exist_ok=True)
        self.generators_path.mkdir(parents=True, exist_ok=True)
        self.reviewers_path.mkdir(parents=True, exist_ok=True)
        self.tools_path.mkdir(parents=True, exist_ok=True)

        self.registry = self._load_registry()

    def _load_registry(self) -> dict:
        """Cargar registro de agentes"""
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                return json.load(f)
        return {"agentes": {}, "herramientas": {}}

    def _save_registry(self):
        """Guardar registro de agentes"""
        with open(self.registry_file, "w") as f:
            json.dump(self.registry, f, indent=2)

    def activar_agente(self, nombre_agente: str) -> bool:
        """Activar un agente"""
        if nombre_agente not in self.registry["agentes"].get(
            "creadores", {}
        ) and nombre_agente not in self.registry["agentes"].get("revisores", {}):
            logger.error(f"Agente no encontrado: {nombre_agente}")
            return False

        # Mover de inactive a active
        agente_file = self.inactive_path / f"{nombre_agente}.py"
        if agente_file.exists():
            destino = self.active_path / f"{nombre_agente}.py"
            shutil.move(str(agente_file), str(destino))

        # Actualizar registro
        grupo = (
            "creadores"
            if nombre_agente in self.registry["agentes"].get("creadores", {})
            else "revisores"
        )
        self.registry["agentes"][grupo][nombre_agente]["estado"] = "activo"
        self.registry["agentes"][grupo][nombre_agente]["ultima_activacion"] = (
            datetime.now().isoformat()
        )
        self._save_registry()

        logger.info(f"Agente activado: {nombre_agente}")
        return True

    def desactivar_agente(self, nombre_agente: str) -> bool:
        """Desactivar un agente"""
        if nombre_agente not in self.registry["agentes"].get(
            "creadores", {}
        ) and nombre_agente not in self.registry["agentes"].get("revisores", {}):
            logger.error(f"Agente no encontrado: {nombre_agente}")
            return False

        # Mover de active a inactive
        agente_file = self.active_path / f"{nombre_agente}.py"
        if agente_file.exists():
            destino = self.inactive_path / f"{nombre_agente}.py"
            shutil.move(str(agente_file), str(destino))

        # Actualizar registro
        grupo = (
            "creadores"
            if nombre_agente in self.registry["agentes"].get("creadores", {})
            else "revisores"
        )
        self.registry["agentes"][grupo][nombre_agente]["estado"] = "inactivo"
        self._save_registry()

        logger.info(f"Agente desactivado: {nombre_agente}")
        return True

    def generar_codigo(self, especificacion: str, tipo_codigo: str) -> str | None:
        """Generar código usando el agente apropiado"""
        # Seleccionar agente apropiado según tipo
        agente_map = {
            "python": "agente_creador_codigo_python",
            "javascript": "agente_creador_codigo_javascript",
            "sql": "agente_creador_codigo_sql",
            "html": "agente_creador_codigo_html",
            "api": "agente_creador_codigo_api",
            "microservicios": "agente_creador_codigo_microservicios",
            "ml": "agente_creador_codigo_ml",
            "data": "agente_creador_codigo_data",
            "devops": "agente_creador_codigo_devops",
            "seguridad": "agente_creador_codigo_seguridad",
        }

        nombre_agente = agente_map.get(tipo_codigo)
        if not nombre_agente:
            logger.error(f"Tipo de código no soportado: {tipo_codigo}")
            return None

        # Activar agente si no está activo
        if self.registry["agentes"]["creadores"][nombre_agente]["estado"] == "inactivo":
            self.activar_agente(nombre_agente)

        # Ejecutar agente (simulado por ahora)
        logger.info(f"Generando código con {nombre_agente}")
        codigo = f"# Código generado por {nombre_agente}\n# Especificación: {especificacion}\n\ndef main():\n    pass\n"

        # Guardar en historial
        self._guardar_historial(nombre_agente, especificacion, codigo)

        # Actualizar uso
        self.registry["agentes"]["creadores"][nombre_agente]["uso_total"] += 1
        self._save_registry()

        return codigo

    def revisar_codigo(self, codigo: str) -> dict:
        """Revisar código usando agentes revisores"""
        resultados = {}

        # Importar agentes revisores
        from core.code_agents.reviewers.agente_revisor_codigo import agente_revisor_codigo
        from core.code_agents.reviewers.agente_revisor_compatibilidad import (
            agente_revisor_compatibilidad,
        )
        from core.code_agents.reviewers.agente_revisor_rendimiento import agente_revisor_rendimiento
        from core.code_agents.reviewers.agente_revisor_seguridad import agente_revisor_seguridad

        revisores = {
            "agente_revisor_codigo": agente_revisor_codigo,
            "agente_revisor_seguridad": agente_revisor_seguridad,
            "agente_revisor_rendimiento": agente_revisor_rendimiento,
            "agente_revisor_compatibilidad": agente_revisor_compatibilidad,
        }

        for nombre_agente, agente in revisores.items():
            # Activar agente si no está activo
            if self.registry["agentes"]["revisores"][nombre_agente]["estado"] == "inactivo":
                self.activar_agente(nombre_agente)

            # Ejecutar revisión
            logger.info(f"Revisando código con {nombre_agente}")
            resultados[nombre_agente] = agente.revisar(codigo)

            # Actualizar uso
            self.registry["agentes"]["revisores"][nombre_agente]["uso_total"] += 1
            self._save_registry()

        return resultados

    def _guardar_historial(self, agente: str, especificacion: str, codigo: str):
        """Guardar en historial"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        historial_dir = self.history_path / agente / timestamp
        historial_dir.mkdir(parents=True, exist_ok=True)

        # Guardar código
        codigo_file = historial_dir / "codigo.py"
        codigo_file.write_text(codigo)

        # Guardar metadatos
        metadata = {
            "agente": agente,
            "especificacion": especificacion,
            "timestamp": datetime.now().isoformat(),
            "tamano_codigo": len(codigo),
        }

        metadata_file = historial_dir / "metadata.json"
        with open(metadata_file, "w") as f:
            json.dump(metadata, f, indent=2)

        logger.info(f"Historial guardado: {historial_dir}")

    def obtener_estado(self) -> dict:
        """Obtener estado del sistema"""
        return {
            "agentes_activos": len(
                [
                    a
                    for a in self.registry["agentes"].get("creadores", {}).values()
                    if a["estado"] == "activo"
                ]
            ),
            "agentes_inactivos": len(
                [
                    a
                    for a in self.registry["agentes"].get("creadores", {}).values()
                    if a["estado"] == "inactivo"
                ]
            ),
            "revisores_activos": len(
                [
                    a
                    for a in self.registry["agentes"].get("revisores", {}).values()
                    if a["estado"] == "activo"
                ]
            ),
            "herramientas_instaladas": len(
                [h for h in self.registry["herramientas"].values() if h["instalado"]]
            ),
        }


# Instancia global
code_agents_orchestrator = CodeAgentsOrchestrator()

if __name__ == "__main__":
    orchestrator = CodeAgentsOrchestrator()
    estado = orchestrator.obtener_estado()

    print("=== ESTADO DEL SISTEMA DE AGENTES DE CÓDIGO ===")
    print(f"Agentes activos: {estado['agentes_activos']}")
    print(f"Agentes inactivos: {estado['agentes_inactivos']}")
    print(f"Revisores activos: {estado['revisores_activos']}")
    print(f"Herramientas instaladas: {estado['herramientas_instaladas']}")
