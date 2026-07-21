"""Repara errores en 3 niveles: determinista → LLM rápido → LLM potente."""

import json
import logging
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from core.agents.constants import RUFF, SCRIPTS, URA_ROOT
from motor.core.llm import generate as _generate

log = logging.getLogger("ura.multi_agent.reparador")


class AgenteReparador:
    """Repara errores en 3 niveles: determinista → LLM rápido → LLM potente."""

    def reparar(self, archivo: str, errores: list) -> tuple[bool, int, str]:
        ruta = Path(archivo) if isinstance(archivo, str) else archivo
        if not ruta.exists():
            return False, -1, "Archivo no encontrado"

        backup = ruta.with_suffix(".bak_repair")
        if not backup.exists():
            shutil.copy2(ruta, backup)

        reparado = self._nivel_1(ruta)
        if reparado:
            return True, 1, "Reparado por auto_reglas (determinista)"

        reparado = self._nivel_2(ruta, "deepseek-coder:6.7b")
        if reparado:
            return True, 2, "Reparado por DeepSeek 6.7B (LLM rápido)"

        reparado = self._nivel_3(ruta)
        if reparado:
            return True, 3, "Reparado por OpenCode 32B (LLM potente)"

        return False, 0, "No se pudo reparar (watermark creado)"

    def _nivel_1(self, ruta: Path) -> bool:
        try:
            subprocess.run(
                [sys.executable, str(SCRIPTS / "auto_reglas.py"), "--aplicar", str(ruta)],
                capture_output=True,
                timeout=15,
                cwd=str(URA_ROOT),
                check=False,
            )
            subprocess.run([RUFF, "check", "--fix", str(ruta)], capture_output=True, timeout=15, check=False)
            subprocess.run([RUFF, "format", str(ruta)], capture_output=True, timeout=10, check=False)
            compile(ruta.read_text(), str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_1 repair for %s", ruta)
            return False

    def _nivel_2(self, ruta: Path, modelo: str) -> bool:
        try:
            codigo = ruta.read_text()
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", str(ruta)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            if r.returncode == 0:
                return True

            errores = r.stderr or r.stdout or ""
            prompt = (
                f"Repara los siguientes errores de Python SIN cambiar la lógica:\n\n"
                f"ERRORES:\n{errores[:2000]}\n\n"
                f"CODIGO:\n```python\n{codigo[:6000]}\n```\n\n"
                f"Devuelve SOLO el código reparado."
            )

            fixed = _generate(
                prompt,
                model=modelo,
                options={"temperature": 0.0, "num_predict": 4096},
            )

            if fixed and "```" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0] if "```python" in fixed else fixed.split("```")[1]

            ruta.write_text(fixed)
            compile(fixed, str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_2 repair for %s", ruta)
            return False

    def _nivel_3(self, ruta: Path) -> bool:
        try:
            codigo = ruta.read_text()
            r = subprocess.run(
                [RUFF, "check", "--select", "F821", str(ruta)],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )

            payload = json.dumps(
                {
                    "model": "ollama/qwen3:32b-q8_0",
                    "messages": [
                        {
                            "role": "system",
                            "content": "Eres un reparador de código Python. Solo devuelves código corregido.",
                        },
                        {
                            "role": "user",
                            "content": f"Repara SIN cambiar lógica:\n{r.stderr or ''}\n\n```python\n{codigo[:6000]}\n```",
                        },
                    ],
                    "temperature": 0.0,
                },
            ).encode()
            req = urllib.request.Request(
                "http://localhost:8081/v1/chat/completions",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=180) as resp:  # noqa: S310
                fixed = json.loads(resp.read())["choices"][0]["message"]["content"]

            if fixed and "```" in fixed:
                fixed = fixed.split("```python")[1].split("```")[0] if "```python" in fixed else fixed.split("```")[1]

            ruta.write_text(fixed)
            compile(fixed, str(ruta), "exec")
            return True
        except Exception:
            log.exception("Error in nivel_3 repair for %s", ruta)
            return False
