#!/usr/bin/env python3
"""auditd_alerts.py — Puente auditd → journald → ura alerta.

Lee eventos de auditd en los ultimos N minutos y los inyecta
como ALERTA en journald para que `ura alerta` los recoja.

uso:
  python3 scripts/pro/auditd_alerts.py                    # ultimos 5 min
  python3 scripts/pro/auditd_alerts.py --minutes 30       # ventana personalizada
  python3 scripts/pro/auditd_alerts.py --dry-run          # solo muestra, no alerta
"""

import argparse, json, logging, subprocess, sys
from datetime import datetime, timedelta, timezone

log = logging.getLogger("ura.auditd_bridge")

ALERT_LOG = logging.getLogger("ura.alerta")
ALERT_LOG.setLevel(logging.ERROR)
if not ALERT_LOG.handlers:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    ALERT_LOG.addHandler(h)

ALERTAS = []


def ausearch(minutes: int) -> list[dict]:
    """Busca eventos auditd en la ventana de tiempo."""
    since = (datetime.now(timezone.utc) - timedelta(minutes=minutes)).strftime(
        "%H:%M:%S"
    )
    try:
        r = subprocess.run(
            ["sudo", "ausearch", "-k", "ura_motor_changes", "-ts", since, "-i"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        return _parsear(r.stdout)
    except subprocess.TimeoutExpired:
        log.warning("ausearch timeout")
        return []
    except FileNotFoundError:
        log.warning("ausearch no disponible (auditd instalado?)")
        return []


def _parsear(raw: str) -> list[dict]:
    eventos = []
    bloque = {}
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("type=SYSCALL"):
            if bloque:
                eventos.append(bloque)
            bloque = {"raw_type": "SYSCALL"}
        elif line.startswith("type=CWD"):
            if bloque:
                bloque["cwd"] = line.split("cwd=")[-1].strip()
        elif line.startswith("type=PATH"):
            if "name=" in line:
                bloque["path"] = line.split("name=")[-1].split()[0].strip()
        elif line.startswith("type=PROCTITLE"):
            if "proctitle=" in line:
                bloque["comando"] = (
                    line.split("proctitle=")[-1].strip().replace(",", " ")[:120]
                )
    if bloque:
        eventos.append(bloque)
    return eventos


def alertar(eventos: list[dict], dry_run: bool = False):
    for ev in eventos:
        comando = ev.get("comando", "?")
        path = ev.get("path", "?")
        msg = f"AUDITD cambio en motor/: cmd={comando} path={path}"
        if dry_run:
            print(f"[DRY-RUN] {msg}")
            continue
        ALERT_LOG.error("ALERTA %s", msg)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--minutes", type=int, default=5)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    eventos = ausearch(args.minutes)
    if not eventos:
        print(json.dumps({"ok": True, "eventos": 0, "msj": "sin eventos"}))
        return

    alertar(eventos, dry_run=args.dry_run)
    print(
        json.dumps(
            {"ok": True, "eventos": len(eventos), "alertas_lanzadas": len(eventos)},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
