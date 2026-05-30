#!/usr/bin/env python3
"""refactor_duplicados_v2.py — Analisis y limpieza segura de duplicados core/ vs agents/"""

import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

REPO = Path.home() / "URA/ura_ia_1972"
CORE = REPO / "core"
AGENTS = REPO / "agents"
ARCHIVE = REPO / "archive/duplicados_automerge"
BACKUP = REPO / f"archive/backup_{datetime.now():%Y%m%d_%H%M%S}"
TS = datetime.now().strftime("%Y%m%d_%H%M%S")
OUT_JSON = REPO / f"docs/refactor_duplicados_{TS}.json"
OUT_LOG = REPO / f"docs/refactor_duplicados_{TS}.log"
DRY_RUN = "--dry-run" in sys.argv

ARCHIVE.mkdir(parents=True, exist_ok=True)
BACKUP.mkdir(parents=True, exist_ok=True)
OUT_JSON.parent.mkdir(parents=True, exist_ok=True)

log_lines = [f"Analisis seguro de duplicados core/ vs agents/ — {TS}"]
results = []
checked = 0

for core_file in sorted(CORE.glob("*.py")):
    agent_file = AGENTS / core_file.name
    if not agent_file.exists():
        continue

    checked += 1
    c_bytes = core_file.read_bytes()
    a_bytes = agent_file.read_bytes()
    identico = c_bytes == a_bytes

    if identico:
        tipo = "IDENTICO"
        accion = "movido"
        motivo = "duplicado exacto"
        dest = ARCHIVE / core_file.name
        if DRY_RUN:
            log_lines.append(f"SIMULACION  {core_file.name}: se moveria a archive/")
        else:
            shutil.copy2(str(agent_file), str(BACKUP / core_file.name))
            agent_file.rename(dest)
            log_lines.append(f"MOVIDO  {core_file.name}: a archive/ (backup en {BACKUP})")
    else:
        cl = c_bytes.count(b"\n") or 1
        al = a_bytes.count(b"\n") or 1
        ml = max(cl, al)
        diff = sum(
            1 for a, b in zip(c_bytes.splitlines(), a_bytes.splitlines(), strict=False) if a != b
        )
        diff += abs(cl - al)
        pct = min(diff * 100 // ml, 100)
        tipo = f"SIMILAR_{pct}pct" if pct < 20 else f"DIFERENTE_{pct}pct"
        accion = "pendiente"
        motivo = f"revision manual ({tipo})"
        log_lines.append(f"PENDIENTE  {core_file.name}: {tipo}")

    results.append(
        {
            "archivo": core_file.name,
            "accion": accion,
            "motivo": motivo,
            "tipo": tipo,
        }
    )

with open(OUT_LOG, "w") as f:
    f.write("\n".join(log_lines) + "\n")
with open(OUT_JSON, "w") as f:
    json.dump(results, f, indent=2)

movidos = sum(1 for r in results if r["accion"] == "movido")
pendientes = sum(1 for r in results if r["accion"] == "pendiente")

print("\n=== RESUMEN ===")
print(f"  MOVIDOS a archive/:  {movidos}")
print(f"  PENDIENTES (revision): {pendientes}")
print(f"  TOTAL duplicados:    {len(results)}")
print(f"  CHECKED:             {checked}")
print(f"\n  JSON: {OUT_JSON.relative_to(REPO)}")
print(f"  LOG:  {OUT_LOG.relative_to(REPO)}")
