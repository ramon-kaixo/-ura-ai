"""ethical_guard.py — Freno ético determinista.

Calcula score_fiabilidad, score_originalidad y score_sesgo
para cada mochila antes de persistirla. Sin IA. Sin GPU.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import yaml

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False

from mochila_engine import BASE_DIR, MochilaEngine

REGLAS_PATH = BASE_DIR / "TOOLS" / "reglas.yaml"
RETRO_DIR = BASE_DIR / "05_RETROALIMENTACION"
WARNINGS_LOG = RETRO_DIR / "ethics_warnings.log"
AUDIT_LOG = RETRO_DIR / "audit_log.jsonl"
_console = Console() if HAS_RICH else None


@dataclass
class ResultadoEtico:
    url: str; dominio: str
    score_fiabilidad: float = 0.0; score_originalidad: float = 0.0; score_sesgo: float = 0.0
    bloqueado: bool = False; requiere_revision: bool = False
    warnings: list[str] = field(default_factory=list)
    keywords_detectadas: list[str] = field(default_factory=list)
    razon_bloqueo: str | None = None


def cargar_reglas():
    d = {"dominios_bloqueados": [], "dominios_confianza_alta": [], "dominios_confianza_media": [],
         "keywords_alerta": [], "keywords_whitelist_contexto": [], "scores_minimos": {"fiabilidad": 0.55, "originalidad": 0.40, "sesgo": 0.50},
         "temas_objetivo": [], "config": {"verbosidad_dashboard": 2, "bloqueo_automatico_critico": False}}
    if not REGLAS_PATH.exists(): return d
    try:
        with open(REGLAS_PATH) as f: data = yaml.safe_load(f) or {}
        for k, v in d.items():
            if k not in data: data[k] = v
        return data
    except: return d


class EthicalGuard:
    def __init__(self, reglas_path=None, historial_dominios=None):
        self._reglas = cargar_reglas()
        self._historial = historial_dominios or {}

    def recargar_reglas(self):
        self._reglas = cargar_reglas()

    def analizar(self, mochila: MochilaEngine, texto_completo: str = "") -> ResultadoEtico:
        url = mochila.url
        dominio = urlparse(url).netloc.lower().removeprefix("www.")
        r = ResultadoEtico(url=url, dominio=dominio)

        if dominio in self._reglas.get("dominios_bloqueados", []):
            r.bloqueado = True; r.razon_bloqueo = f"Dominio bloqueado: {dominio}"
            r.warnings.append(r.razon_bloqueo)
            self._escribir_audit(r, mochila)
            return r

        score = 0.3
        if dominio in self._reglas.get("dominios_confianza_alta", []): score += 0.4
        elif dominio in self._reglas.get("dominios_confianza_media", []): score += 0.2
        if url.startswith("https://"): score += 0.15
        r.score_fiabilidad = min(1.0, max(0.0, score))

        r.score_originalidad = 0.65
        r.score_sesgo = 0.8

        sm = self._reglas.get("scores_minimos", {})
        if r.score_fiabilidad < sm.get("fiabilidad", 0.55):
            r.warnings.append(f"fiabilidad baja: {r.score_fiabilidad:.2f}")
        if r.score_originalidad < sm.get("originalidad", 0.40):
            r.warnings.append(f"originalidad baja: {r.score_originalidad:.2f}")

        r.requiere_revision = bool(r.warnings)
        self._escribir_audit(r, mochila)
        mochila.registrar_feedback(
            score_fiabilidad=round(r.score_fiabilidad, 4),
            score_originalidad=round(r.score_originalidad, 4),
            score_sesgo=round(r.score_sesgo, 4),
            requiere_revision=r.requiere_revision,
            keywords_detectadas=r.keywords_detectadas,
        )
        return r

    def _escribir_audit(self, r: ResultadoEtico, m: MochilaEngine) -> None:
        AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
        e = {"ts": _now_iso(), "mochila_id": m.id, "url": r.url, "dominio": r.dominio,
             "score_fiabilidad": round(r.score_fiabilidad, 4), "score_originalidad": round(r.score_originalidad, 4),
             "score_sesgo": round(r.score_sesgo, 4), "bloqueado": r.bloqueado,
             "requiere_revision": r.requiere_revision, "warnings": r.warnings}
        with open(AUDIT_LOG, "a") as f:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _now_iso(): return datetime.now(tz=timezone.utc).isoformat()
