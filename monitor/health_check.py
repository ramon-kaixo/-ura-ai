#!/usr/bin/env python3
"""Health Check v2 — Diagnóstico completo del GX10.
Mide: disco, RAM, carga CPU, VRAM Ollama, latencia SSH/HTTP.
"""

import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from core.config_manager import CONFIG

TARGET = CONFIG["ollama"]["host"]
OLLAMA_PORT = CONFIG["ollama"]["port"]
SSH_USER = CONFIG["ssh"]["user"]
SSH_TIMEOUT = 15

ALERT_FILE = Path.home() / "URA" / "logs" / "health_alerts.log"
ALERT_FILE.parent.mkdir(parents=True, exist_ok=True)

DISK_THRESHOLD_GB = 10
DISK_THRESHOLD_PCT = 95
RAM_THRESHOLD_GB = 4
LOAD_THRESHOLD = 8


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


def measure_ssh_latency() -> float:
    """Mide latencia SSH en ms."""
    start = time.time()
    try:
        subprocess.run(  # noqa: S603  -- constante, solo mide latencia SSH
            ["ssh", "-o", "ConnectTimeout=5", "-o", "BatchMode=yes", f"{SSH_USER}@{TARGET}", "echo ok"],  # noqa: S607
            capture_output=True,
            timeout=5,
            check=False,
        )
        return (time.time() - start) * 1000
    except Exception:
        return -1


def measure_http_latency() -> float:
    """Mide latencia HTTP Ollama en ms."""
    try:
        import urllib.request

        start = time.time()
        url = f"http://{TARGET}:{OLLAMA_PORT}/api/tags"
        req = urllib.request.Request(url)
        req.add_header("Connection", "close")
        with urllib.request.urlopen(req, timeout=5):
            return (time.time() - start) * 1000
    except Exception:
        return -1


def check_disk() -> list:
    alerts = []
    stats = {}
    output = ssh_run("df -h / /home /opt 2>/dev/null")
    if not output:
        alerts.append("No se pudo obtener uso de disco")
        return alerts, stats

    for line in output.split("\n")[1:]:
        parts = line.split()
        if len(parts) < 5:
            continue
        mount = parts[5]
        pct_str = parts[4].replace("%", "")
        avail = parts[3]
        used_s = parts[2]
        total_s = parts[1]
        try:
            pct = int(pct_str)
        except ValueError:
            continue

        stats[mount] = {"used": used_s, "avail": avail, "total": total_s, "pct": pct}

        if pct >= DISK_THRESHOLD_PCT:
            alerts.append(f"Disco {mount}: {pct}% usado (límite {DISK_THRESHOLD_PCT}%)")
        if avail.endswith("G"):
            try:
                gb = float(avail[:-1])
                if gb < DISK_THRESHOLD_GB:
                    alerts.append(f"Disco {mount}: solo {gb:.1f}GB libres")
            except ValueError:
                pass
    return alerts, stats


def check_ram() -> list:
    alerts = []
    stats = {}
    output = ssh_run("free -h 2>/dev/null | grep -E 'Mem|Swap'")
    if not output:
        return alerts, stats

    for line in output.split("\n"):
        parts = line.split()
        if len(parts) < 4:
            continue
        name = parts[0].replace(":", "")
        total = parts[1]
        used = parts[2]
        avail = parts[3] if len(parts) > 3 else "?"
        stats[name] = {"total": total, "used": used, "avail": avail}

        if name == "Mem":
            try:
                avail_num = float(avail.replace("Gi", "").replace("G", "").replace("Mi", "").replace("M", ""))
                if "Mi" in avail or "M" in avail:
                    avail_num /= 1024
                if avail_num < RAM_THRESHOLD_GB:
                    alerts.append(f"RAM baja: {avail_num:.1f}G disponibles")
            except ValueError:
                pass
    return alerts, stats


def check_load() -> list:
    alerts = []
    stats = {}
    output = ssh_run("uptime 2>/dev/null")
    if not output:
        return alerts, stats

    if "load average" in output:
        load_part = output.split("load average:")[-1].strip()
        loads = [float(x.replace(",", "")) for x in load_part.split()[:3]]
        stats["load"] = loads
        if loads[0] > LOAD_THRESHOLD:
            alerts.append(f"CPU load alta: {loads[0]:.1f} (límite {LOAD_THRESHOLD})")
    return alerts, stats


def check_ollama_models() -> list:
    models = []
    output = ssh_run("ollama ps 2>/dev/null")
    if not output:
        return models

    for line in output.strip().split("\n")[1:]:
        parts = line.split()
        if parts:
            models.append({"model": parts[0], "size": parts[2] if len(parts) > 2 else "?"})
    return models


def main() -> int:

    all_alerts = []

    # Latencia
    measure_ssh_latency()
    measure_http_latency()

    # Disco
    disk_alerts, disk_stats = check_disk()
    for _mount, _s in disk_stats.items():
        pass
    for _a in disk_alerts:
        pass
    all_alerts.extend(disk_alerts)

    # RAM
    ram_alerts, ram_stats = check_ram()
    for _name, _s in ram_stats.items():
        pass
    for _a in ram_alerts:
        pass
    all_alerts.extend(ram_alerts)

    # CPU
    load_alerts, load_stats = check_load()
    if "load" in load_stats:
        pass
    for _a in load_alerts:
        pass
    all_alerts.extend(load_alerts)

    # Ollama
    models = check_ollama_models()
    if models:
        for _m in models:
            pass
        all_alerts.append(f"{len(models)} modelos cargados")
    else:
        all_alerts.append("Ningún modelo cargado en Ollama")

    # Resumen
    if [a for a in all_alerts if "⚠" not in a and "modelo" not in a.lower()]:
        timestamp = datetime.now(UTC).isoformat()
        with open(ALERT_FILE, "a") as f:
            f.write(f"[{timestamp}] {'\n'.join(all_alerts)}\n")
    else:
        pass

    # Latencia resumen

    return 0 if not [a for a in all_alerts if "⚠" in a] else 1


if __name__ == "__main__":
    sys.exit(main())
