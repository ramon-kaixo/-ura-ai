#!/usr/bin/env python3
"""
Rodillo 0 — Pre-vuelo de Instalación (Tuneladora URA-DEVSECOPS-2026)
Refactorizado estructural — Complejidad máxima por función < B(10)
"""

import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(os.environ.get("REPO_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))
INVENTORY_PATH = REPO_ROOT / "config" / "network_inventory.json"
DOCKER_COMPOSE_PATH = REPO_ROOT / "docker-compose.sandbox.yml"
RESERVED_PORTS = {11434, 5052, 8080, 3000}
ALLOWED_PORT_RANGE = (1024, 65535)
PYPI_CACHE = {}


# ── Carga de inventario ──────────────────────────────────────────
def load_inventory():
    if not INVENTORY_PATH.exists():
        return {"agents": [], "services": {}, "ips_in_use": [], "ports_in_use": []}
    with open(INVENTORY_PATH) as f:
        return json.load(f)


def save_inventory(data):
    with open(INVENTORY_PATH, "w") as f:
        json.dump(data, f, indent=2)


def load_docker_ports():
    ports = set()
    if not DOCKER_COMPOSE_PATH.exists():
        return ports
    content = DOCKER_COMPOSE_PATH.read_text()
    for m in re.finditer(r'-\s*"?(\d+):\d+"?', content):
        ports.add(int(m.group(1)))
    return ports


def load_active_connections():
    ports = set()
    try:
        r = subprocess.run(
            ["lsof", "-iTCP", "-sTCP:LISTEN", "-P", "-n"], capture_output=True, text=True, timeout=5
        )
        for line in r.stdout.splitlines():
            for part in line.split():
                if ":" in part and not part.startswith("COMMAND"):
                    try:
                        ports.add(int(part.split(":")[-1]))
                    except ValueError:
                        continue
    except Exception:
        pass
    return ports


# ── check_ips() — Pure function < B(10) ─────────────────────────
def check_ips(file_path, existing_ips):
    ips = set()
    ip_pat = re.compile(r"\b(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})\b")
    with open(file_path, errors="ignore") as f:
        for line in f:
            for m in ip_pat.finditer(line):
                ip = m.group(1)
                if ip not in ("0.0.0.0", "127.0.0.1", "255.255.255.255"):
                    ips.add(ip)
    report = []
    for ip in ips:
        if ip in existing_ips:
            report.append((ip, "conflicto"))
        else:
            report.append((ip, "nueva"))
    return report, ips


# ── check_ports() — Pure function < B(10) ───────────────────────
def check_ports(file_path, used_ports):
    ports = set()
    port_pat = re.compile(r"(?:port|PORT|listen|bind)\s*[=:]\s*(\d{2,5})")
    with open(file_path, errors="ignore") as f:
        for line in f:
            for m in port_pat.finditer(line):
                p = int(m.group(1))
                if p < 65536:
                    ports.add(p)
    report = []
    for p in ports:
        if p in used_ports:
            alt = p + 1
            while alt in used_ports and alt < ALLOWED_PORT_RANGE[1]:
                alt += 1
            report.append((p, "en_uso", alt))
        elif p < ALLOWED_PORT_RANGE[0]:
            report.append((p, "privilegiado", None))
        else:
            report.append((p, "libre", None))
        used_ports.add(p)
    return report


# ── check_agents() — Pure function < B(10) ──────────────────────
def check_agent_ids(file_path, existing_ids):
    ids = set()
    id_pat = re.compile(r'agent_id\s*[=:]\s*["\']([^"\']+)["\']')
    with open(file_path, errors="ignore") as f:
        for line in f:
            for m in id_pat.finditer(line):
                ids.add(m.group(1))
    report = []
    for aid in ids:
        if aid in existing_ids:
            suffix = 2
            while f"{aid}_{suffix}" in existing_ids:
                suffix += 1
            report.append((aid, "duplicado", f"{aid}_{suffix}"))
        else:
            report.append((aid, "nuevo", None))
        existing_ids.add(aid)
    return report


# ── check_dependencies() — Pure function < B(10) ────────────────
def check_dependencies(file_path):
    missing = set()
    with open(file_path, errors="ignore") as f:
        for line in f:
            m = re.match(r"^(?:import|from)\s+(\w+)", line.strip())
            if m:
                r = subprocess.run(
                    ["python3", "-c", f"import {m.group(1)}"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if r.returncode != 0:
                    missing.add(m.group(1))
    return missing


def check_pypi(package_name):
    if package_name in PYPI_CACHE:
        return PYPI_CACHE[package_name]
    try:
        url = f"https://pypi.org/pypi/{package_name}/json"
        req = urllib.request.Request(url, headers={"User-Agent": "Tuneladora-URA/4.0"})
        urllib.request.urlopen(req, timeout=5)  # nosec B310
        PYPI_CACHE[package_name] = None
    except Exception:
        PYPI_CACHE[package_name] = f"Paquete '{package_name}' no encontrado"
    return PYPI_CACHE[package_name]


# ── Procesadores individuales (< 10 líneas cada uno) ────────────
def _process_ips(f, existing_ips, report):
    ips, new_ips = check_ips(f, existing_ips)
    for ip, st in ips:
        report.append(
            (f"   {'🔴' if st == 'conflicto' else '🟢'} {f.name}: IP {ip}", st == "conflicto")
        )
        if st == "conflicto":
            return True
    existing_ips |= new_ips
    return False


def _process_ports(f, used_ports, report, all_files):
    crit = False
    for p, st, alt in check_ports(f, used_ports):
        if st == "en_uso" and f.name in {Path(fp).name for fp in all_files}:
            report.append((f"   🟢 {f.name}: Puerto {p} (auto-definido, ok)", False))
        elif st == "en_uso":
            report.append((f"   🔴 {f.name}: Puerto {p} en uso → sugerido {alt}", True))
            crit = True
        elif st == "privilegiado":
            report.append((f"   🔴 {f.name}: Puerto {p} privilegiado", True))
            crit = True
        else:
            report.append((f"   🟢 {f.name}: Puerto {p} libre", False))
    return crit


def _process_agents(f, existing_ids, report):
    for aid, st, sug in check_agent_ids(f, existing_ids):
        if st == "duplicado":
            report.append((f"   🔴 {f.name}: ID '{aid}' duplicado → sugerido {sug}", True))
            return True
        report.append((f"   🟢 {f.name}: ID '{aid}' nuevo", False))
    return False


# ── Coordinador (< B(10) ────────────────────────────────────────
def preflight_check(files):
    files = list(files)
    inv = load_inventory()
    used_ports = load_docker_ports() | load_active_connections() | RESERVED_PORTS
    existing_ids = {a.get("id") for a in inv.get("agents", [])}
    existing_ips = set(inv.get("ips_in_use", []))
    raw = []

    for fp in files:
        f = Path(fp)
        if not f.exists() or f.suffix != ".py" or "legacy" in str(f) or "tests" in str(f.parent):
            continue
        if _process_ips(f, existing_ips, raw):
            continue
        _process_ports(f, used_ports, raw, files)
        _process_agents(f, existing_ids, raw)
        for dep in check_dependencies(f):
            raw.append((f"   🟡 {f.name}: dependencia '{dep}' faltante", False))

    inv["ips_in_use"] = list(existing_ips)
    save_inventory(inv)
    critical = any(c for _, c in raw)
    return (not critical, [m for m, _ in raw])


# ── Entry point ──────────────────────────────────────────────────
if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: preflight_check.py <archivo1> [archivo2 ...]")
        sys.exit(0)
    passed, report = preflight_check(sys.argv[1:])
    print(f"\n🛫 RODILLO 0: {'✅ SUPERADO' if passed else '🔴 BLOQUEADO'}")
    for msg in report:
        print(msg)
    sys.exit(0 if passed else 1)
