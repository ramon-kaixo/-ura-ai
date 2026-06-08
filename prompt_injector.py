"""prompt_injector.py — Aduana de seguridad."""
import json, re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from mochila_engine import BASE_DIR

RETRO_DIR = BASE_DIR / "05_RETROALIMENTACION"
LOG_PATH = RETRO_DIR / "injection_log.jsonl"

PATRONES = [
    re.compile(r"ignora\s+las\s+instrucciones?\s+anteriores?", re.I),
    re.compile(r"eres\s+(ahora|un)\s+asistente\s+(malvado|sin\s+restricciones)", re.I),
    re.compile(r"system\s*:\s*.*reasign", re.I),
]

@dataclass
class Resultado:
    texto_sanitizado: str; url: str; n_patrones_detectados: int; patrones_activados: list[str]; timestamp: str

class JailbreakGuard:
    def __init__(self, registrar_log=True): self._log = registrar_log
    def sanitizar(self, texto, url=""):
        act = [p.pattern for p in PATRONES if p.search(texto)]
        t = texto
        for p in PATRONES:
            t = p.sub("[NEUTRALIZADO]", t)
        r = Resultado(f"<user_input>\n{t}\n</user_input>", url, len(act), act, datetime.now(tz=timezone.utc).isoformat())
        if self._log and act:
            LOG_PATH.parent.mkdir(parents=True,exist_ok=True)
            with LOG_PATH.open("a") as f: f.write(json.dumps({"t":r.timestamp,"n":r.n_patrones_detectados})+"\n")
        return r
