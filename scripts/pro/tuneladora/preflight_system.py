#!/usr/bin/env python3
"""Pre-flight check: evita duplicados de servicios, puertos, screens.

Uso:
  preflight_system.py install <service> [port] [screen]
  preflight_system.py audit
"""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

MANIFEST = Path("/home/ramon/URA/ura_ia_1972/deploy/system_manifest.json")
UID = os.getuid()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, check=False)


def check_systemd_service(name: str) -> dict:
    result: dict = {"exists": False, "active": False, "scopes": []}
    for scope in ("system", "user"):
        flag = ["--user"] if scope == "user" else []
        r = _run(["systemctl", "show", *flag, f"{name}.service", "--property=LoadState", "--value"])
        load_state = r.stdout.strip()
        if load_state != "loaded":
            continue
        result["exists"] = True
        r2 = _run(["systemctl", *flag, "is-active", f"{name}.service"])
        status = r2.stdout.strip()
        if status in ("active", "activating"):
            result["active"] = True
            result["scopes"].append(scope)
        else:
            result["scopes"].append(f"{scope}({status})")
    return result


def check_port(port: int) -> dict:
    r = _run(["ss", "-tlnp"])
    result: dict = {"in_use": False, "process": None}
    port_str = str(port)
    for line in r.stdout.splitlines():
        if "LISTEN" not in line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        addr_port = local_addr.rsplit(":", 1)[-1]
        if addr_port != port_str:
            continue
        result["in_use"] = True
        m = re.search(r'users:\(\((.*?)\)\)', line)
        if m:
            result["process"] = m.group(1)[:80]
        break
    return result


def check_screen_exists(name: str) -> bool:
    r = _run(["screen", "-ls"])
    return name in r.stdout


def load_manifest() -> dict:
    if not MANIFEST.exists():
        return {}
    return json.loads(MANIFEST.read_text())


def check_manifest_service(manifest: dict, name: str) -> dict | None:
    for cat in ("services.system", "services.user"):
        data: dict = manifest
        for k in cat.split("."):
            data = data.get(k, {})
        if name in data:
            return data[name]
    return None


def preflight(service_name: str, port: int | None = None, screen: str | None = None) -> bool:
    print(f"Pre-flight: {service_name}")
    ok = True

    manifest = load_manifest()
    existing = check_manifest_service(manifest, service_name)
    if existing:
        desc = existing.get("description", "N/A")
        p = existing.get("port", "N/A")
        print(f"  Ya existe en manifiesto: {desc} (puerto: {p})")
        ok = False

    svc = check_systemd_service(service_name)
    if svc["exists"]:
        print(f"  Servicio ya existe en systemd: {svc['scopes']}")
        ok = False

    if port:
        p = check_port(port)
        if p["in_use"]:
            print(f"  Puerto {port} ya en uso por: {p['process'] or 'desconocido'}")
            port_owner = manifest.get("ports", {}).get(str(port))
            if port_owner:
                print(f"  Manifiesto dice: {port_owner}")
            ok = False

    if screen and check_screen_exists(screen):
        print(f"  Screen '{screen}' ya existe")
        ok = False

    if ok:
        print("  OK para instalar")
    else:
        print("  ABORTANDO — duplicado detectado")
    return ok


def _ss_ports(output: str) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    for line in output.splitlines():
        if "LISTEN" not in line:
            continue
        parts = line.split()
        if len(parts) < 4:
            continue
        local_addr = parts[3]
        port = local_addr.rsplit(":", 1)[-1]
        if port.isdigit():
            result.append((port, line.strip()[:80]))
    return result


def _audit_services(manifest: dict, issues: list[str]) -> None:
    for name, info in manifest.get("services", {}).get("system", {}).items():
        svc = check_systemd_service(name)
        if not svc["exists"]:
            issues.append(f"Servicio '{name}' en manifiesto pero NO en systemd")
            continue
        expected = "active" if info.get("status") == "active" else None
        if expected and not svc["active"]:
            issues.append(f"Servicio '{name}' en manifiesto como active pero NO activo en systemd")
        port_val = info.get("port")
        if not port_val:
            continue
        for raw in str(port_val).split("/"):
            p_clean = raw.strip()
            if not p_clean or p_clean == "null":
                continue
            try:
                pp = check_port(int(p_clean))
                if not pp["in_use"]:
                    issues.append(f"Puerto {p_clean} para '{name}' libre (deberia estar en uso)")
            except ValueError:
                pass


def _audit_ports(manifest: dict, issues: list[str]) -> None:
    r = _run(["ss", "-tlnp"])
    used_ports: set[str] = set()
    unregistered: list[str] = []
    for port, line in _ss_ports(r.stdout):
        if "tailscaled" in line:
            continue
        if "docker-proxy" in line and port not in ("3080", "6333", "6334", "9093"):
            continue
        used_ports.add(port)
        if port not in manifest.get("ports", {}):
            unregistered.append(f"Puerto {port} en uso pero NO en manifiesto")

    mkports = set(manifest.get("ports", {}).keys())
    orphaned = sorted(
        [p for p in mkports - used_ports if p.isdigit() and p not in ("53", "631", "9050")],
        key=lambda x: int(x),
    )
    issues.extend(unregistered)
    if orphaned:
        issues.append(f"Puertos en manifiesto pero no escuchando: {', '.join(orphaned[:5])}")


def audit_current_state() -> dict:
    print("AUDIT: Comparando sistema vs manifiesto...")
    issues: list[str] = []

    if not MANIFEST.exists():
        print("  Manifiesto no existe")
        return {"manifest_exists": False, "issues": issues}

    manifest = json.loads(MANIFEST.read_text())
    _audit_services(manifest, issues)
    _audit_ports(manifest, issues)

    if issues:
        print(f"  {len(issues)} discrepancias encontradas:")
        for i in issues:
            print(f"    - {i}")
    else:
        print("  Sistema coincide con manifiesto")
    return {"manifest_exists": True, "issues": issues}


def _main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd == "audit":
        audit_current_state()
        sys.exit(0)

    if cmd == "install":
        if len(sys.argv) < 3:
            print("Falta nombre del servicio")
            sys.exit(1)
        service = sys.argv[2]
        port = int(sys.argv[3]) if len(sys.argv) > 3 else None
        screen = sys.argv[4] if len(sys.argv) > 4 else None
        ok = preflight(service, port, screen)
        sys.exit(0 if ok else 1)

    print(f"Comando desconocido: {cmd}")
    sys.exit(1)


if __name__ == "__main__":
    _main()
