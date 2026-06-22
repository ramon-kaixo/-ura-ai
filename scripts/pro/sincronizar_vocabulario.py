#!/usr/bin/env python3
"""Sincronización bidireccional SSH del vocabulario de corrección de voz entre Mac y ASUS.

Flujo:
  1. Exporta DB local (Mac) → volcado SQL → SCP → importa en ASUS (GB10)
  2. Exporta DB remota (ASUS) → SSH .dump → importa en local (Mac)

Usa INSERT OR IGNORE para evitar colisiones de primary key.
Ejecutar via cron cada 5 minutos en Mac:
  */5 * * * * /usr/bin/python3 /Users/ramonesnaola/URA/ura_ia_1972/scripts/pro/sincronizar_vocabulario.py >> /Users/ramonesnaola/URA/ura_ia_1972/logs/sync.log 2>&1
"""

import os
import sqlite3
import subprocess
import sys

# ── Configuración ──────────────────────────────────────────────────
BASE = "/Users/ramonesnaola/URA/ura_ia_1972"
DB_LOCAL = os.path.join(BASE, "config/voice_corrections.db")
DUMP_LOCAL = "/tmp/vocabulario_mac.sql"
DUMP_REMOTO = "/tmp/vocabulario_asus.sql"

ASUS_SSH = "ramon@10.164.1.99"
DB_ASUS = "/home/ramon/URA/ura_ia_1972/config/voice_corrections.db"
# ───────────────────────────────────────────────────────────────────


def _dump_conn(conn) -> str:
    """Genera volcado SQL con INSERT OR IGNORE desde una conexión."""
    lines = []
    for line in conn.iterdump():
        line = line.replace('INSERT INTO "', 'INSERT OR IGNORE INTO "')
        line = line.replace("INSERT INTO ", "INSERT OR IGNORE INTO ")
        lines.append(line)
    return "\n".join(lines)


def sincronizar() -> None:

    # 1. Local → Remoto
    if os.path.exists(DB_LOCAL):
        with sqlite3.connect(DB_LOCAL) as conn:
            dump = _dump_conn(conn)
        with open(DUMP_LOCAL, "w") as f:
            f.write(dump)

        subprocess.run(
            ["scp", DUMP_LOCAL, f"{ASUS_SSH}:{DUMP_REMOTO}"],
            check=True,
            capture_output=True,
        )
        cmd = f"sqlite3 {DB_ASUS} < {DUMP_REMOTO} && rm {DUMP_REMOTO}"
        subprocess.run(["ssh", ASUS_SSH, cmd], check=True, capture_output=True)

    # 2. Remoto → Local
    result = subprocess.run(
        ["ssh", ASUS_SSH, f"sqlite3 {DB_ASUS} .dump"],
        capture_output=True,
        text=True,
        check=True,
    )
    with open(DUMP_LOCAL, "w") as f:
        for line in result.stdout.splitlines():
            line = line.replace('INSERT INTO "', 'INSERT OR IGNORE INTO "')
            line = line.replace("INSERT INTO ", "INSERT OR IGNORE INTO ")
            f.write(line + "\n")

    with sqlite3.connect(DB_LOCAL) as conn, open(DUMP_LOCAL) as f:
        conn.executescript(f.read())

    os.remove(DUMP_LOCAL)


if __name__ == "__main__":
    try:
        sincronizar()
    except Exception:
        sys.exit(1)
