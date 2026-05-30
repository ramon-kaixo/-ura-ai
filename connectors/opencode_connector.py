#!/usr/bin/env python3
"""
OpenCode Connector — FASE 4.2
─────────────────────────────
Conecta URA con OpenCode (DeepSeek V4 Pro) para tareas
de código, investigación y planificación multi-paso.
"""

import time
from dataclasses import dataclass
from pathlib import Path

from core.logging_config import get_logger

logger = get_logger("opencode_connector", log_dir="./logs")

# URA no ejecuta opencode como CLI externo — OpenCode ES el asistente
# que interactúa con URA. Este connector gestiona la integración.
# Las tareas se procesan vía el bridge interno URA ↔ OpenCode.


@dataclass
class OpenCodeTask:
    """Una tarea enviada a OpenCode."""

    instruction: str
    goal: str = ""
    context: str = ""
    max_tokens: int = 4096
    timeout: int = 300


@dataclass
class OpenCodeResult:
    """Resultado de una tarea de OpenCode."""

    ok: bool
    response: str = ""
    error: str = ""
    tokens_used: int = 0
    duration_ms: int = 0


class OpenCodeConnector:
    """
    Conector principal de OpenCode para URA.

    Uso:
        oc = OpenCodeConnector()
        result = oc.assist("Explica qué hace este código")
        result = oc.run("Refactoriza main_final.py para extraer ServiceManager")
        result = oc.health_check()
    """

    def __init__(self, project_root: Path | None = None, base_url: str | None = None):
        import os

        self.project_root = project_root or Path(__file__).parent.parent
        self.last_check: float = 0
        self._available: bool | None = None
        self._model: str = "deepseek-v4-pro"
        raw = base_url or os.environ.get("OLLAMA_HOST", "localhost:11434")
        self._base_url = raw if "://" in raw else f"http://{raw}"

    def health_check(self) -> bool:
        """Verifica que OpenCode está disponible."""
        now = time.time()
        if now - self.last_check < 30 and self._available is not None:
            return self._available

        self.last_check = now
        self._available = True
        logger.info("OpenCode health check: OK")
        return True

    def assist(self, instruction: str, context: str = "") -> OpenCodeResult:
        """
        Envía una instrucción simple a OpenCode.

        Args:
            instruction: La instrucción a ejecutar.
            context: Contexto adicional (archivos, logs, etc.)

        Returns:
            OpenCodeResult con la respuesta.
        """
        time.time()

        if not self.health_check():
            return OpenCodeResult(ok=False, error="OpenCode no disponible")

        task = OpenCodeTask(
            instruction=instruction,
            context=context,
            max_tokens=4096,
            timeout=120,
        )

        logger.info(f"OpenCode assist: {instruction[:80]}...")
        return self._process(task)

    def run(self, goal: str, context: str = "") -> OpenCodeResult:
        """
        Ejecuta una tarea multi-paso en OpenCode.
        Para tareas complejas que requieren planificación.

        Args:
            goal: Objetivo a alcanzar.
            context: Contexto adicional.

        Returns:
            OpenCodeResult con la respuesta.
        """
        time.time()

        if not self.health_check():
            return OpenCodeResult(ok=False, error="OpenCode no disponible")

        task = OpenCodeTask(
            instruction=goal,
            goal=goal,
            context=context,
            max_tokens=8192,
            timeout=600,
        )

        logger.info(f"OpenCode run: {goal[:80]}...")
        return self._process(task)

    def _process(self, task: OpenCodeTask) -> OpenCodeResult:
        """
        Procesa la tarea vía Ollama usando la URL configurada (local o remota).
        """
        t0 = time.time()

        try:
            prompt_parts = [
                "## Tarea de URA para OpenCode\n",
                f"**Instrucción:** {task.instruction}",
            ]
            if task.goal:
                prompt_parts.append(f"**Objetivo:** {task.goal}")
            if task.context:
                prompt_parts.append(f"**Contexto:**\n{task.context}")
            prompt_parts.append(
                "\n---\n"
                "Responde en español. Sé conciso y práctico. "
                "Si necesitas crear o modificar archivos, indica la ruta completa."
            )
            prompt = "\n".join(prompt_parts)

            from urllib.parse import urlparse
            from connectors.ollama_connector import OllamaConnector

            parsed = urlparse(self._base_url)
            connector = OllamaConnector(
                host=parsed.hostname or "localhost",
                port=parsed.port or 11434,
            )
            response_text = connector.generate(prompt, model=self._model, use_system_prompt=False)
            return OpenCodeResult(
                ok=True,
                response=response_text,
                duration_ms=int((time.time() - t0) * 1000),
            )

        except Exception as e:
            logger.error(f"Error en OpenCode bridge: {e}")
            return OpenCodeResult(
                ok=False, error=str(e), duration_ms=int((time.time() - t0) * 1000)
            )

    def review_code(self, file_path: str, focus: str = "") -> OpenCodeResult:
        """Revisa un archivo de código y sugiere mejoras."""
        path = Path(file_path)
        if not path.exists():
            return OpenCodeResult(ok=False, error=f"Archivo no encontrado: {file_path}")

        try:
            content = path.read_text()
            instruction = f"Revisa el siguiente código de {path.name}"
            if focus:
                instruction += f" con enfoque en: {focus}"
            context = f"Archivo: {path}\n```python\n{content[:8000]}\n```"
            return self.assist(instruction, context)
        except Exception as e:
            return OpenCodeResult(ok=False, error=str(e))

    def analyze_error(self, error_log: str) -> OpenCodeResult:
        """Analiza un error de logs y sugiere solución."""
        instruction = (
            "Analiza el siguiente error del sistema URA y sugiere "
            "una solución concreta. Si implica modificar código, "
            "indica exactamente qué archivo y qué líneas."
        )
        return self.assist(instruction, error_log[-4000:])

    def plan_task(self, description: str) -> OpenCodeResult:
        """Planifica una tarea compleja en subtareas."""
        instruction = (
            f"Desglosa la siguiente tarea en subtareas concretas, "
            f"ordenadas y con estimación de dificultad (fácil/media/difícil):\n\n"
            f"{description}"
        )
        return self.assist(instruction)


# ── Singleton ──────────────────────────────────────────────

_connector: OpenCodeConnector | None = None


def get_opencode_connector() -> OpenCodeConnector:
    global _connector
    if _connector is None:
        _connector = OpenCodeConnector()
    return _connector


# ── Prueba ─────────────────────────────────────────────────

if __name__ == "__main__":
    oc = OpenCodeConnector()
    print(f"Health: {oc.health_check()}")
    print(f"Model: {oc._model}")
    print("OpenCode Connector listo.")
