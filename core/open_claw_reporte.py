#!/usr/bin/env python3
"""open_claw_reporte.py — Reporte estandarizado multiplataforma."""
from __future__ import annotations
import json, os, platform, subprocess
from datetime import datetime, timezone
from pathlib import Path
HOME = Path.home()
REPORTS_DIR = HOME / "URA" / "ura_ia_1972" / "reports"
COLA_DIR = (HOME / ".nervioso" / "ura_search" / "cola" / "hetzner").resolve()
if not COLA_DIR.exists(): COLA_DIR = (HOME / "URA" / "storage" / "inbox").resolve()
if not str(COLA_DIR).startswith(str(HOME.resolve())):
    raise PermissionError("COLA_DIR fuera del home del usuario")
def get_ram_libre_gb() -> float:
    if platform.system() == "Darwin":
        try: out = subprocess.getoutput("sysctl hw.memsize | awk '{print $2}'"); return round(int(out) / (1024**3), 1)
        except: return 0.0
    else:
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if "MemAvailable" in line: return round(int(line.split()[1]) / 1024 / 1024, 1)
        except: pass
        return 0.0
def get_disco_libre_gb() -> float:
    try: st = os.statvfs('/'); return round((st.f_bavail * st.f_frsize) / (1024**3), 1)
    except: return 0.0
def get_agentes_activos() -> int:
    try: out = subprocess.check_output(["ps", "aux"], text=True).count("open_claw"); return max(0, out - 2)
    except: return 0
def get_cola_pendiente() -> int:
    if COLA_DIR.exists(): return len(list(COLA_DIR.iterdir()))
    return 0
def get_ultimo_audit() -> str:
    try: reports = sorted(REPORTS_DIR.glob("*.json"), key=os.path.getmtime, reverse=True); return reports[0].name if reports else "N/A"
    except: return "N/A"
def generar_reporte() -> dict:
    ram = get_ram_libre_gb(); agentes = get_agentes_activos()
    return {"nodo": platform.node(), "os": platform.system(), "timestamp": datetime.now(tz=timezone.utc).isoformat(), "recursos": {"ram_disponible_gb": ram, "disco_libre_gb": get_disco_libre_gb()}, "agentes_activos": agentes, "cola_pendiente": get_cola_pendiente(), "ultimo_audit": get_ultimo_audit(), "estado": "OK" if agentes > 0 else "IDLE"}
if __name__ == "__main__": print(json.dumps(generar_reporte(), indent=2))
