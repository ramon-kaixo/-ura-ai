#!/usr/bin/env python3
"""open_claw_coordinador.py — Mini-orquestador elastico. Envia reportes a URA."""
from __future__ import annotations
import json, platform, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from core.open_claw_reporte import generar_reporte

URA_ENDPOINT = "http://127.0.0.1:4096/reporte"
LOG_DIR = Path.home() / "URA" / "logs"
REPORTS_DIR = Path.home() / "URA" / "ura_ia_1972" / "reports"

def enviar_reporte(reporte: dict) -> bool:
    """Envia el reporte a URA via HTTP POST."""
    try:
        import urllib.request
        data = json.dumps(reporte).encode()
        req = urllib.request.Request(
            URA_ENDPOINT, data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        return False

def guardar_local(reporte: dict) -> Path:
    """Guarda el reporte localmente como respaldo."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    path = LOG_DIR / f"reporte_{platform.node()}_{datetime.now().strftime('%Y%m%d')}.json"
    path.write_text(json.dumps(reporte, indent=2))
    return path

def ejecutar_ciclo() -> dict:
    """Ciclo completo: generar reporte, enviar a URA, guardar local."""
    reporte = generar_reporte()
    log_path = guardar_local(reporte)
    
    if enviar_reporte(reporte):
        reporte["envio"] = "OK"
    else:
        reporte["envio"] = "FALLIDO"
        # Fallback: guardar en reports/ para el scp nocturno
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        (REPORTS_DIR / f"reporte_offline_{platform.node()}.json").write_text(
            json.dumps(reporte, indent=2)
        )
    
    reporte["log_local"] = str(log_path)
    return reporte

if __name__ == "__main__":
    r = ejecutar_ciclo()
    print(json.dumps(r, indent=2))
    sys.exit(0 if r.get("envio") == "OK" else 1)
