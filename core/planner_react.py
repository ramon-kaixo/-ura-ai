import json
import logging
from typing import Any

from core.vision.state_verifier import StateVerifier

logger = logging.getLogger("ReActPlanner")


class ReActPlanner:
    def __init__(self, laia_agent: Any) -> None:
        self.agent = laia_agent
        self.verifier = StateVerifier()
        self.max_iteraciones = 5

    def ejecutar_objetivo(self, objetivo: str, app_name: str) -> bool:
        contexto: dict[str, Any] = {
            "objetivo": objetivo,
            "app": app_name,
            "historial": [],
            "paso": 0,
        }
        for _ in range(self.max_iteraciones):
            accion = self._pensar(contexto)
            if not accion:
                return False
            exito = self._actuar(accion, app_name)
            if self._objetivo_cumplido(contexto):
                return True
            contexto["historial"].append({"accion": accion, "exito": exito})
            contexto["paso"] += 1
        return False

    def _pensar(self, contexto: dict[str, Any]) -> dict[str, Any] | None:
        prompt = (
            f"Objetivo: {contexto['objetivo']}\n"
            f"Historial de acciones: {json.dumps(contexto['historial'])}\n"
            f"Decide la siguiente acción (formato JSON): "
            f'{{"action": "click", "target": "texto del botón"}} o {{"action": "write", "text": "..."}}\n'
            f"Solo JSON."
        )
        try:
            respuesta = self.agent._llm_plan(prompt)
            return json.loads(respuesta)
        except Exception as exc:
            logger.error("Error pensando: %s", exc)
            return None

    def _actuar(self, accion: dict[str, Any], app_name: str) -> bool:
        if accion.get("action") == "click":
            return self.agent.click_smart(accion.get("target", ""))
        if accion.get("action") == "write":
            self.agent.executor.write(accion.get("text", ""))
            return True
        return False

    def _objetivo_cumplido(self, contexto: dict[str, Any]) -> bool:
        prompt = f"Objetivo: {contexto['objetivo']}\n¿Se logró? Responde sí/no."
        try:
            respuesta = self.agent._llm_plan(prompt)
            return "sí" in respuesta.lower()
        except Exception as exc:
            logger.error("Error verificando objetivo: %s", exc)
            return False
