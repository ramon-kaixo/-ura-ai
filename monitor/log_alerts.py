#!/usr/bin/env python3
"""Log Alerts v2 — Centraliza y de-duplica errores críticos desde GX10.
Usa hash de contenido para no reportar el mismo error dos veces.
"""

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from core.config_manager import CONFIG

TARGET = CONFIG["ollama"]["host"]
SSH_USER = CONFIG["ssh"]["user"]
SSH_TIMEOUT = 15

REMOTE_LOG_DIRS = ["/opt/ura/logs", "/opt/ura/logs/maintenance"]
LOCAL_ALERTS_DIR = Path.home() / "URA" / "logs" / "alerts_gx10"
LOCAL_ALERTS_DIR.mkdir(parents=True, exist_ok=True)

SEEN_HASHES_FILE = LOCAL_ALERTS_DIR / ".seen_hashes.json"
MAX_SEEN = 500  # máximo de hashes guardados para evitar crecimiento infinito

PATTERNS = ["ERROR", "CRITICAL", "FATAL", "CRASH", "Traceback", "Exception", "Segfault", "OOM", "Killed", "Panic"]


def ssh_run(cmd: str) -> str:
    try:
        result = subprocess.run(
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", f"{SSH_USER}@{TARGET}", cmd],
            capture_output=True,
            text=True,
            timeout=SSH_TIMEOUT,
            check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def load_seen_hashes() -> set:
    if SEEN_HASHES_FILE.exists():
        try:
            return set(json.loads(SEEN_HASHES_FILE.read_text()))
        except Exception:  # noqa: S110
            pass
    return set()


def save_seen_hashes(hashes: set) -> None:
    # Mantener solo los últimos MAX_SEEN
    hashes_list = list(hashes)[-MAX_SEEN:]
    SEEN_HASHES_FILE.write_text(json.dumps(hashes_list))


def hash_line(line: str) -> str:
    """Hash normalizado: ignora timestamp, solo contenido semántico."""
    # Eliminar prefijo de archivo y timestamp para normalizar
    parts = line.split(":", 2)
    core = parts[-1].strip() if len(parts) > 2 else line.strip()
    core = core.split(" - ", 1)[-1] if " - " in core else core
    return hashlib.sha256(core.encode()).hexdigest()[:16]


def fetch_critical_logs() -> list:
    critical = []
    cmd_parts = []
    for d in REMOTE_LOG_DIRS:
        for p in PATTERNS:
            cmd_parts.append(f"grep -r '{p}' {d}/*.log 2>/dev/null")  # noqa: PERF401
    cmd = "(" + "\n".join(cmd_parts) + ") 2>/dev/null | sort -u | tail -200"

    output = ssh_run(cmd)
    if output:
        for line in output.strip().split("\n"):
            if line.strip():
                critical.append(line.strip())  # noqa: PERF401
    return critical


def main() -> int:

    seen = load_seen_hashes()
    critical = fetch_critical_logs()

    if not critical:
        return 0

    new_alerts = []
    duplicates = 0
    for line in critical:
        h = hash_line(line)
        if h not in seen:
            new_alerts.append(line)
            seen.add(h)
        else:
            duplicates += 1

    if new_alerts:
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        alert_file = LOCAL_ALERTS_DIR / f"gx10_critical_{timestamp}.log"
        with open(alert_file, "w") as f:  # noqa: PTH123
            for line in new_alerts:
                f.write(line + "\n")
        save_seen_hashes(seen)

        # Agrupar por tipo
        from collections import Counter

        types = Counter()
        for line in new_alerts:
            for p in PATTERNS:
                if p in line:
                    types[p] += 1
                    break

        for _t, _c in types.most_common(5):
            pass

        if len(new_alerts) <= 10:
            for line in new_alerts:  # noqa: B007
                pass
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
