#!/usr/bin/env python3
"""Agente de Musica — Registra y analiza historial de reproduccion via Maloja."""

import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "URA" / "ura_ia_1972"
MALOJA_URL = "http://localhost:42010/apis/mlj_1"


def obtener_historial(limit=20):
    try:
        r = subprocess.run(
            ["curl", "-s", f"{MALOJA_URL}/scrobbles?limit={limit}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if r.returncode == 0:
            data = json.loads(r.stdout)
            return data.get("list", data.get("scrobbles", []))
    except:
        pass
    return []


if __name__ == "__main__":
    historial = obtener_historial()
    out = BASE / "docs" / "musica" / f"historial_{datetime.now().strftime('%Y%m%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(historial, f, ensure_ascii=False, indent=2)
    print(f"OK {len(historial)} temas en {out.name}")
    for s in historial[:5]:
        t = s.get("track", {})
        print(f"  {t.get('artists', ['?'])[0]} — {t.get('title', '?')}")
