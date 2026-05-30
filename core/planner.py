import json
import logging
import os
import subprocess

logger = logging.getLogger(__name__)

GX10_URL = os.getenv("GX10_URL", "http://10.164.1.99:11434/api/chat")
MODEL_CODIFICACION = os.getenv("MODEL_CODIFICACION", "qwen3:32b")


class TaskPlanner:
    def __init__(self) -> None:
        pass

    def plan(self, goal: str) -> list[dict]:
        prompt = (
            f"Descompone esta tarea en pasos simples (maximo 5) que pueda ejecutar "
            f"un script de automatizacion (clics, escribir, esperar, leer pantalla). "
            f"Tarea: {goal}\n"
            f"Devuelve solo JSON, ejemplo: "
            f'[{{"action":"click","target":"Exportar"}},{{"action":"wait","seconds":2}},'
            f'{{"action":"type","text":"informe.csv"}}]'
        )
        payload = json.dumps(
            {
                "model": MODEL_CODIFICACION,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
            }
        )
        try:
            resp = subprocess.run(
                ["curl", "-s", GX10_URL, "-d", payload],
                capture_output=True,
                text=True,
                timeout=30,
            )
            data = json.loads(resp.stdout)
            content = data["message"]["content"]
            plan = json.loads(content)
            if isinstance(plan, list):
                logger.info("Plan generado: %d pasos", len(plan))
                return plan
        except Exception as exc:
            logger.error("Planificacion fallo: %s", exc)
        return [{"action": "fail", "reason": "no se pudo planificar"}]

    def execute_plan(self, plan: list[dict], executor: object, reader: object) -> bool:
        for step in plan:
            action = step.get("action", "")
            if action == "click":
                target = step.get("target", "")
                if target:
                    ok = executor.click_smart(target, reader)
                    if not ok:
                        logger.error("Paso click fallo: %s", target)
                        return False
            elif action == "type":
                executor.write(step.get("text", ""))
            elif action == "wait":
                import time

                time.sleep(step.get("seconds", 1))
            elif action == "screenshot":
                executor.screenshot(step.get("path", "screenshot.png"))
            elif action == "fail":
                logger.error("Plan fallo: %s", step.get("reason", ""))
                return False
        return True
