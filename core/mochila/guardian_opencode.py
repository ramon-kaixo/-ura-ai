import difflib
import json
import logging
import re
import shutil
import subprocess

logger = logging.getLogger("mochila.guardian")


class OpenCodeGuardian:
    def __init__(self, req_id: str = "") -> None:
        self._req_id = req_id
        self._ultimo_pattern: str | None = None
        self.vagancy_patterns = [
            r"(?i)(//|#|/\*)\s*\.\.\.\s*(rest|resto|remaining|continuation|code|implementation|function)",
            r"(?i)(//|#)\s*(same\s+as|igual\s+que)\s*(above|before|anterior)",
            r"(?i)(//|#)\s*(unchanged|sin\s+cambios)",
            r"(?i)<--\s*rest\s*of\s*the\s*template\s*-->",
            r"(?im)^[ \t]*(//|#)\s*\.\.\.\s*$",
        ]

    def evaluar_texto_stream(self, text_window: str) -> bool:
        score = 0
        for pattern in self.vagancy_patterns:
            m = re.search(pattern, text_window, re.MULTILINE)
            if m:
                score += 1
                self._ultimo_pattern = m.group(0)
            if score >= 2:
                return False
        return True

    def generar_penalizacion(self) -> str:
        if not self._ultimo_pattern:
            return ""
        return (
            f"[RECHAZO DE INFRAESTRUCTURA: En tu intento anterior "
            f"usaste la cadena exacta '{self._ultimo_pattern}'. "
            f"Tienes prohibido repetir esa estructura.]"
        )

    def validar_diff(
        self,
        original: str,
        generado: str,
    ) -> tuple[bool, list[str]]:
        diff = difflib.unified_diff(
            original.splitlines(keepends=True),
            generado.splitlines(keepends=True),
            lineterm="",
        )
        problematicas = []
        for line in diff:
            if line.startswith("+"):
                for pat in self.vagancy_patterns:
                    if re.search(pat, line[1:], re.MULTILINE):
                        problematicas.append(line[1:].strip())
                        break
        return len(problematicas) < 2, problematicas

    def verificar_sintaxis_final(self, file_path: str, raw_content: str) -> bool:
        clean_content = raw_content.strip()
        if not clean_content or len(clean_content.splitlines()) < 3:
            return False

        if file_path.endswith(".py"):
            try:
                res = subprocess.run(  # noqa: PLW1510
                    ["python3", "-m", "py_compile", file_path],
                    capture_output=True,
                    timeout=5,
                )
                return res.returncode == 0
            except subprocess.TimeoutExpired:
                return False

        elif file_path.endswith(".sh"):
            if shutil.which("bash"):
                res = subprocess.run(  # noqa: PLW1510
                    ["bash", "-n", file_path],
                    capture_output=True,
                    timeout=5,
                )
                return res.returncode == 0

        elif file_path.endswith(".json"):
            try:
                json.loads(raw_content)
                return True
            except json.JSONDecodeError:
                return False

        elif file_path.endswith((".yaml", ".yml")):
            try:
                import yaml

                yaml.safe_load(raw_content)
                return True
            except (ImportError, Exception):
                return ":" in raw_content

        return True
