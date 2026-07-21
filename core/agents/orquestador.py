"""Decide qué acción tomar según el estado del sistema. Modelo: Qwen 14B."""

import logging

from core.agents.constants import MODELOS, URA_ROOT

log = logging.getLogger("ura.multi_agent.orquestador")


class AgenteOrquestador:
    """Decide qué acción tomar según el estado del sistema. Modelo: Qwen 14B."""

    MODELO = MODELOS["orquestador"]

    def decidir(self, telemetria: dict, conciencia: dict) -> tuple[str, str]:
        ram = telemetria.get("hardware", {}).get("ram_pct", 0)
        f821 = telemetria.get("f821", 99)

        if ram > 85:
            return "PAUSAR", f"RAM al {ram}%, esperando a que baje"

        if f821 > 10:
            return "REPARAR", f"{f821} F821 detectados, lanzando reparador"

        funciones_pendientes = self._contar_pendientes()
        if funciones_pendientes > 0 and ram < 85:
            return "REFACTORIZAR", f"{funciones_pendientes} funciones pendientes"

        return "ESPERAR", "Sistema estable, sin acciones necesarias"

    @staticmethod
    def _contar_pendientes() -> int:
        import ast

        total = 0
        try:
            for py_file in URA_ROOT.rglob("*.py"):
                p = str(py_file)
                if any(x in p for x in ["/.venv/", "/.git/", "/backups/", "/site-packages/"]):
                    continue
                try:
                    tree = ast.parse(py_file.read_text())
                    for node in ast.walk(tree):
                        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and hasattr(node, "end_lineno") and node.end_lineno and node.lineno and node.end_lineno - node.lineno > 80:
                            total += 1
                except Exception as e:
                    log.warning("Error parseando AST en %s: %s", py_file, e)
        except Exception as e:
            log.warning("Error contando funciones pendientes: %s", e)
        return total
