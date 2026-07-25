"""Sofía — revisora LLM determinística post-estática, pre-commit."""
from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field

import requests

from scripts.pro.tuneladora.config import Configuration

log = logging.getLogger("tuneladora.sofia")

_SOFIA_DIFF_MARKER = "___SOFIA_DIFF___"
_SOFIA_TESTS_MARKER = "___SOFIA_TESTS___"
_SOFIA_API_MARKER = "___SOFIA_API___"

SOFIA_PROMPT = f"""Eres un revisor de código senior. Revisa el siguiente diff:

{_SOFIA_DIFF_MARKER}

Tests modificados:
{_SOFIA_TESTS_MARKER}

API changes:
{_SOFIA_API_MARKER}

Responde ÚNICAMENTE con un JSON con esta estructura:
{{
    "hallazgos": [
        {{
            "tipo": "critico" | "advertencia" | "info",
            "archivo": "ruta/archivo.py",
            "linea": 42,
            "mensaje": "descripción clara",
            "sugerencia": "cómo arreglarlo"
        }}
    ],
    "resumen": "texto corto del hallazgo principal"
}}

Reglas:
- Temperatura: 0 (determinista)
- No alucines líneas: cada hallazgo debe citar código real del diff
- Si el diff está vacío, responde {{"hallazgos": [], "resumen": "sin cambios"}}
- No inventes issues que no existen
- JSON válido, sin markdown ni comillas extra"""


@dataclass
class SofiaHallazgo:
    tipo: str
    archivo: str
    linea: int
    mensaje: str
    sugerencia: str = ""


@dataclass
class SofiaReport:
    hallazgos: list[SofiaHallazgo] = field(default_factory=list)
    resumen: str = ""
    modelo: str = ""
    duracion_ms: float = 0.0
    n_criticos: int = 0
    n_advertencias: int = 0


class Sofia:
    def __init__(self, cfg: Configuration) -> None:
        self.cfg = cfg
        self._model = getattr(cfg, "sofia_model", "qwen2.5-coder:14b")

    def should_review(self, diff: str, api_diff: str, tests_modified: bool, n_files: int) -> bool:
        if not diff.strip() and not api_diff.strip():
            return False
        if n_files > 10 or len(diff) > 10000:
            return True
        if tests_modified:
            return True
        return bool(api_diff.strip())

    def review(self, diff: str, tests_modified: str = "", api_diff: str = "", n_files: int = 0) -> SofiaReport:
        t0 = time.monotonic()
        report = SofiaReport(modelo=self._model)

        if not self.should_review(diff, api_diff, bool(tests_modified.strip()), n_files):
            return report

        prompt = SOFIA_PROMPT.replace(_SOFIA_DIFF_MARKER, diff[:8000])
        prompt = prompt.replace(_SOFIA_TESTS_MARKER, tests_modified or "(ninguno)")
        prompt = prompt.replace(_SOFIA_API_MARKER, api_diff or "(sin cambios)")

        try:
            r = requests.post(
                f"{self.cfg.ollama_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False,
                       "options": {"temperature": 0, "seed": 42}},
                timeout=self.cfg.timeout_llm,
            )
            r.raise_for_status()
            raw = r.json().get("response", "")
            parsed = self._parse_response(raw)
            if parsed:
                report = parsed
        except Exception as e:
            log.warning("Sofia LLM call failed: %s", e)

        report.duracion_ms = (time.monotonic() - t0) * 1000
        report.modelo = self._model
        report.n_criticos = sum(1 for h in report.hallazgos if h.tipo == "critico")
        report.n_advertencias = sum(1 for h in report.hallazgos if h.tipo == "advertencia")
        log.info("Sofia: %d críticos, %d advertencias en %.0fms",
                 report.n_criticos, report.n_advertencias, report.duracion_ms)
        return report

    def _parse_response(self, raw: str) -> SofiaReport | None:
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    return None
            else:
                return None
        hallazgos = []
        for h in data.get("hallazgos", []):
            hallazgos.append(SofiaHallazgo(
                tipo=h.get("tipo", "info"),
                archivo=h.get("archivo", ""),
                linea=h.get("linea", 0),
                mensaje=h.get("mensaje", ""),
                sugerencia=h.get("sugerencia", ""),
            ))
        return SofiaReport(
            hallazgos=hallazgos,
            resumen=data.get("resumen", ""),
        )
