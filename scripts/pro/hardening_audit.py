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
        ["systemctl", "list-units", "--type=service", "--all", "--no-legend"],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    services = []
    for line in result.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].startswith(URA_PREFIX):
            services.append(parts[0])
    return sorted(set(services))


def check_hardening(service: str) -> dict[str, str]:
    result = subprocess.run(  # noqa: S603
        ["systemctl", "show", service],  # noqa: S607
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    props = {}
    for line in result.stdout.splitlines():
        for check in HARDENING_CHECKS:
            if line.startswith(check + "="):
                props[check] = line.split("=", 1)[1]
    return props


def main() -> int:
    services = get_all_services()

    total = 0
    scored = dict.fromkeys(HARDENING_CHECKS, 0)

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
            for _f in flags:
                pass
        total += score

    for check, count in sorted(scored.items()):  # noqa: B007
        pct = count / len(services) * 100 if services else 0
        "█" * int(pct / 5) + "░" * (20 - int(pct / 5))

    return 0 if total > 0 else 1


if __name__ == "__main__":
    sys.exit(main())
