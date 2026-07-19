#!/usr/bin/env python3
"""URA - Sandbox de Errores.

Sistema para errores que no se pudieron solucionar automáticamente:
- Análisis profundo del error
- Búsqueda de soluciones en base de conocimiento
- Ejecución de soluciones alternativas
- Reporte de resultados para intervención manual
"""

import argparse
import json
import logging
import subprocess
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Ruta del archivo de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config" / "error_sandbox.json"
KNOWLEDGE_BASE_PATH = Path(__file__).parent.parent / "data" / "error_knowledge.json"


@dataclass
class SandboxResult:
    """Resultado del análisis en sandbox."""

    alert_id: str
    error_type: str
    analysis: str
    suggested_solutions: list[str]
    attempted_solutions: list[str]
    successful_solution: str | None
    requires_manual_intervention: bool
    timestamp: str


class ErrorSandbox:
    """Sandbox para análisis de errores no solucionados."""

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path = config_path or CONFIG_PATH
        self.knowledge_base_path = KNOWLEDGE_BASE_PATH
        self.config = self._load_config()
        self.knowledge_base = self._load_knowledge_base()
        self.sandbox_log: list[SandboxResult] = []

    def _load_config(self) -> dict:
        """Cargar configuración desde archivo."""
        try:
            with open(self.config_path) as f:  # noqa: PTH123
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Archivo de configuración no encontrado: {self.config_path}")
            return self._default_config()
        except json.JSONDecodeError as e:
            logger.exception(f"Error decodificando configuración: {e}")
            return self._default_config()

    def _default_config(self) -> dict:
        """Configuración por defecto."""
        return {
            "version": "1.0",
            "max_analysis_time": 60,
            "max_solution_attempts": 5,
            "auto_intervention": False,
            "log_to_file": True,
        }

    def _load_knowledge_base(self) -> dict:
        """Cargar base de conocimiento de errores."""
        try:
            with open(self.knowledge_base_path) as f:  # noqa: PTH123
                return json.load(f)
        except FileNotFoundError:
            logger.warning(f"Base de conocimiento no encontrada: {self.knowledge_base_path}")
            return self._default_knowledge_base()
        except json.JSONDecodeError as e:
            logger.exception(f"Error decodificando base de conocimiento: {e}")
            return self._default_knowledge_base()

    def _default_knowledge_base(self) -> dict:
        """Base de conocimiento por defecto."""
        return {
            "ollama_404": {
                "common_causes": [
                    "Puerto ocupado por otro servicio",
                    "Ollama no está corriendo",
                    "Modelo no descargado",
                    "Configuración incorrecta",
                ],
                "solutions": [
                    "Matar proceso que ocupa el puerto",
                    "Reiniciar Ollama",
                    "Descargar modelo faltante",
                    "Reasignar puerto alternativo",
                ],
            },
            "redis_connection": {
                "common_causes": [
                    "Redis no está corriendo",
                    "Puerto incorrecto",
                    "Autenticación fallida",
                ],
                "solutions": [
                    "Iniciar Redis con brew services start redis",
                    "Verificar configuración de puerto",
                    "Reiniciar Redis",
                ],
            },
            "port_conflict": {
                "common_causes": [
                    "Múltiples servicios usando mismo puerto",
                    "Servicio zombie ocupando puerto",
                    "Docker usando puerto",
                ],
                "solutions": [
                    "Usar port_assigner para encontrar puerto alternativo",
                    "Matar proceso zombie",
                    "Matar proceso Docker",
                ],
            },
        }

    def analyze_error(self, alert_id: str, error_type: str, context: dict) -> SandboxResult:
        """Analizar error en sandbox."""
        logger.info(f"Analizando error {alert_id} en sandbox: {error_type}")

        # Buscar en base de conocimiento
        error_info = self.knowledge_base.get(
            error_type,
            {"common_causes": ["Causa desconocida"], "solutions": ["Revisar logs manualmente"]},
        )

        # Análisis basado en contexto
        analysis = self._generate_analysis(error_type, context, error_info)

        # Sugerir soluciones
        suggested_solutions = error_info["solutions"]

        # Intentar soluciones automáticamente
        attempted_solutions = []
        successful_solution = None

        for solution in suggested_solutions:
            if self._attempt_solution(solution, context):
                attempted_solutions.append(solution)
                successful_solution = solution
                break
            attempted_solutions.append(solution)

        # Determinar si requiere intervención manual
        requires_manual = successful_solution is None

        result = SandboxResult(
            alert_id=alert_id,
            error_type=error_type,
            analysis=analysis,
            suggested_solutions=suggested_solutions,
            attempted_solutions=attempted_solutions,
            successful_solution=successful_solution,
            requires_manual_intervention=requires_manual,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self.sandbox_log.append(result)

        if requires_manual:
            logger.warning(f"Error {alert_id} requiere intervención manual")

        return result

    def _generate_analysis(self, error_type: str, context: dict, error_info: dict) -> str:
        """Generar análisis del error."""
        analysis_parts = [
            f"Tipo de error: {error_type}",
            f"Causas comunes: {', '.join(error_info['common_causes'])}",
        ]

        # Añadir contexto específico
        if "port" in context:
            analysis_parts.append(f"Puerto afectado: {context['port']}")

        if "process" in context:
            analysis_parts.append(f"Proceso involucrado: {context['process']}")

        return " | ".join(analysis_parts)

    def _attempt_solution(self, solution: str, context: dict) -> bool:
        """Intentar aplicar solución."""
        try:
            # Soluciones específicas basadas en keywords
            if "Matar proceso" in solution:
                if "port" in context:
                    # Intentar matar proceso que ocupa el puerto
                    result = subprocess.run(  # noqa: S603  -- puerto desde contexto interno
                        ["lsof", "-ti", f":{context['port']}"],  # noqa: S607  -- puerto desde contexto interno
                        capture_output=True,
                        text=True,
                        timeout=5,
                        check=False,
                    )
                    if result.stdout.strip():
                        pid = result.stdout.strip().split("\n")[0]
                        subprocess.run(["kill", "-9", pid], timeout=5, check=False)  # noqa: S603,S607  -- PID desde salida de lsof, interno
                        time.sleep(1)
                        return True

            elif "Reiniciar Ollama" in solution:
                subprocess.run(["pkill", "-9", "ollama"], timeout=5, check=False)  # noqa: S607  -- comando constante
                time.sleep(2)
                subprocess.Popen(
                    ["ollama", "serve"],  # noqa: S607  -- comando constante
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                time.sleep(3)
                return True

            elif "Iniciar Redis" in solution:
                subprocess.run(
                    ["brew", "services", "start", "redis"],  # noqa: S607  -- comando constante
                    capture_output=True,
                    timeout=10,
                    check=False,
                )
                time.sleep(2)
                return True

            elif "port_assigner" in solution:
                # Usar port_assigner para encontrar puerto alternativo
                from port_assigner import PortAssigner

                assigner = PortAssigner()
                if "port" in context:
                    new_port = assigner.find_best_port(context["port"])
                    return new_port is not None

            return False

        except Exception as e:
            logger.exception(f"Error intentando solución '{solution}': {e}")
            return False

    def get_sandbox_log(self) -> list[SandboxResult]:
        """Obtener log del sandbox."""
        return self.sandbox_log

    def get_manual_intervention_errors(self) -> list[SandboxResult]:
        """Obtener errores que requieren intervención manual."""
        return [r for r in self.sandbox_log if r.requires_manual_intervention]


def main() -> None:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description="URA - Sandbox de Errores")
    parser.add_argument(
        "--analyze",
        nargs=2,
        metavar=("ALERT_ID", "ERROR_TYPE"),
        help="Analizar error",
    )
    parser.add_argument("--log", action="store_true", help="Mostrar log del sandbox")
    parser.add_argument(
        "--manual",
        action="store_true",
        help="Mostrar errores que requieren intervención",
    )
    parser.add_argument("--verbose", action="store_true", help="Modo verboso")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)

    sandbox = ErrorSandbox()

    if args.analyze:
        alert_id, error_type = args.analyze
        result = sandbox.analyze_error(alert_id, error_type, {})

        for _sol in result.suggested_solutions:
            pass
        for _sol in result.attempted_solutions:
            pass
        if result.successful_solution:
            pass
        else:
            pass

    elif args.log:
        log = sandbox.get_sandbox_log()
        for result in log:  # noqa: B007
            pass

    elif args.manual:
        manual_errors = sandbox.get_manual_intervention_errors()
        for result in manual_errors:  # noqa: B007
            pass

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
