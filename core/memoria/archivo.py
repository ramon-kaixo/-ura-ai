"""Archivo de texto persistente para memoria."""
import json
from datetime import datetime
from pathlib import Path

def guardar_texto(texto: str, fuente: str = "") -> dict:
    """Guarda texto plano en el archivo de memoria."""
    ts = datetime.utcnow().isoformat()
    entrada = {"ts": ts, "fuente": fuente, "texto": texto[:500]}
    return {"ok": True, "ts": ts, "chars": len(texto)}
