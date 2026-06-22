#!/usr/bin/env python3
"""hardening_audit.py — Audita el nivel de hardening de todos los servicios systemd URA.

Uso: python3 scripts/pro/hardening_audit.py
"""

import subprocess
import sys

URA_PREFIX = "ura-"
HARDENING_CHECKS = [
    "PrivateTmp",
    "ProtectSystem",
    "ProtectHome",
    "NoNewPrivileges",
    "MemoryDenyWriteExecute",
    "CapabilityBoundingSet",
]


def get_all_services() -> list[str]:
    result = subprocess.run(
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend"],
        capture_output=True, text=True, timeout=10,
    )
    services = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].startswith(URA_PREFIX):
            services.append(parts[0])
    return sorted(set(services))


def check_hardening(service: str) -> dict[str, str]:
    result = subprocess.run(
        ["systemctl", "show", service],
        capture_output=True, text=True, timeout=10,
    )
    props = {}
    for line in result.stdout.splitlines():
        for check in HARDENING_CHECKS:
            if line.startswith(check + "="):
                props[check] = line.split("=", 1)[1]
    return props


def main() -> int:
    services = get_all_services()
    print(f"Auditando {len(services)} servicios URA...\n")

    total = 0
    scored = {s: 0 for s in HARDENING_CHECKS}

    for svc in services:
        props = check_hardening(svc)
        score = 0
        flags = []
        for check in HARDENING_CHECKS:
            val = props.get(check, "missing")
            if val in ("yes", "true", "full"):
                score += 1
                scored[check] += 1
                flags.append(f"  + {check}={val}")
            elif check == "CapabilityBoundingSet" and val != "missing":
                score += 1
                scored[check] += 1
                flags.append(f"  + {check}=custom")

        if flags:
            print(f"{svc}: {score}/{len(HARDENING_CHECKS)}")
            for f in flags:
                print(f)
            print()
        total += score

    print("\n=== Resumen ===")
    print(f"Puntuación total: {total}/{len(services) * len(HARDENING_CHECKS)}")
    print(f"Promedio: {total / len(services):.1f}/{len(HARDENING_CHECKS)}" if services else "N/A")
    print()
    for check, count in sorted(scored.items()):
        pct = count / len(services) * 100 if services else 0
        bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
        print(f"  {check:30s} {bar} {count}/{len(services)} ({pct:.0f}%)")

    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
