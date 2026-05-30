#!/usr/bin/env python3
"""Deployment planner — genera planes de despliegue para nodos nuevos."""

import json
import logging
from pathlib import Path
from typing import Any

import requests

from core.memory.semantic_brain import SemanticBrain
from core.utils import sanitize_log

logger = logging.getLogger("DeploymentPlanner")

GX10_URL = "http://10.164.1.99:11434/api/chat"
MODEL = "qwen2.5-coder:14b"
URA_BASE = Path(__file__).resolve().parent.parent
RECETAS_PATH = URA_BASE / "config" / "deployment_recipes.json"
PLANES_DIR = URA_BASE / "data" / "planes"


class DeploymentPlanner:
    """Genera planes de despliegue usando recetas y memoria semantica."""

    def __init__(self) -> None:
        self.brain = SemanticBrain()
        with open(RECETAS_PATH, encoding="utf-8") as fh:
            self.recetas = json.load(fh)

    def generar_plan(self, nodo_id: str, rol: str, perfil: dict[str, Any]) -> dict[str, Any]:
        """Genera un plan de despliegue para un nodo.

        Args:
            nodo_id: Identificador del nodo.
            rol: Rol asignado al nodo.
            perfil: Perfil tecnico del nodo.

        Returns:
            Diccionario con lista de pasos de despliegue.
        """
        # Punto 12: Seleccionar receta segun arquitectura
        arch = perfil.get("arch", "amd64")
        receta_key = f"{rol}_{arch}" if f"{rol}_{arch}" in self.recetas else rol
        receta = self.recetas.get(receta_key, self.recetas.get("worker", {}))
        memoria = self.brain.buscar_instrucciones(f"desplegar {rol}", "deployment")
        contexto = (
            f"Receta base ({receta_key}): {json.dumps(receta)}\n"
            f"Memoria: {memoria}\n"
            f"Perfil: {json.dumps(perfil)}"
        )
        prompt = (
            f"Genera un plan de despliegue para un nodo {rol} (arquitectura {arch}). "
            f"Devuelve solo JSON con lista 'pasos', cada paso con "
            f"'comando', 'descripcion', 'verificacion' (opcional), 'rollback' (opcional). "
            f"No incluyas comandos destructivos. Si el nodo es Windows, usa PowerShell. "
            f"Contexto: {contexto}"
        )
        payload = {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        try:
            r = requests.post(GX10_URL, json=payload, timeout=60)
            plan = json.loads(r.json()["message"]["content"])
        except Exception as exc:
            logger.warning(sanitize_log(f"Error generando plan con LLM: {exc}"))
            plan = {"pasos": receta.get("pasos", [])}

        # Validacion de seguridad
        for paso in plan.get("pasos", []):
            cmd = paso.get("comando", "")
            if any(forbidden in cmd for forbidden in ["rm -rf /", "shutdown", "reboot"]):
                raise ValueError(f"Comando prohibido en plan: {cmd}")

        # Guardar plan
        PLANES_DIR.mkdir(parents=True, exist_ok=True)
        with open(PLANES_DIR / f"{nodo_id}_plan.json", "w", encoding="utf-8") as fh:
            json.dump(plan, fh, indent=2)

        return plan


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    planner = DeploymentPlanner()
    perfil_test = {
        "hostname": "test-node",
        "ip": "100.100.100.100",
        "so": "Linux",
        "docker": "no",
        "arch": "aarch64",
    }
    plan = planner.generar_plan("test-node", "worker", perfil_test)
    print(json.dumps(plan, indent=2))
