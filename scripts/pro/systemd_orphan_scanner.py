from datetime import UTC
#!/usr/bin/env python3
"""systemd_orphan_scanner.py — Detect orphan systemd units (missing ExecStart).

Scans system and user units. Flags HIGH if the ExecStart binary/script
does not exist on disk, MEDIUM if not executable.

Usage:
  python3 scripts/pro/systemd_orphan_scanner.py            # default: --ura-only
  python3 scripts/pro/systemd_orphan_scanner.py --ura-only
  python3 scripts/pro/systemd_orphan_scanner.py --all
  python3 scripts/pro/systemd_orphan_scanner.py --fix      # disable+delete orphans
  python3 scripts/pro/systemd_orphan_scanner.py --json     # pipeline output
"""

PLUGIN = {
    "name": "systemd_orphan_scanner",
    "phase": "pre",
    "timeout": 30,
    "args": ["--json"],
    "blocking": False,
    "needs_file": False,
}

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

URA_HOME = Path("/home/ramon/URA")
REPO = URA_HOME / "ura_ia_1972"
SYSTEM_UNITS = Path("/etc/systemd/system")
USER_UNITS = Path(os.environ.get("HOME", "/home/ramon")) / ".config/systemd/user"
TIMER_DIRS = ["/etc/systemd/system", str(USER_UNITS)]
SYSTEMD_ANALYZE = shutil.which("systemd-analyze") or ""
SYSTEMCTL = shutil.which("systemctl") or ""


def collect_units() -> dict[str, list[str]]:
    units: dict[str, list[str]] = {"system": [], "user": []}
    if SYSTEM_UNITS.is_dir():
        units["system"] = [str(f) for f in sorted(SYSTEM_UNITS.iterdir()) if f.suffix == ".service"]
    if USER_UNITS.is_dir():
        units["user"] = [str(f) for f in sorted(USER_UNITS.iterdir()) if f.suffix == ".service"]
    return units


def extract_execstart(path: str) -> str | None:
    try:
        with open(path) as f:
            for line in f:
                stripped = line.strip()
                if stripped.startswith("ExecStart="):
                    return stripped[len("ExecStart="):].strip()
                if stripped.startswith("ExecStartPre="):
                    return stripped[len("ExecStartPre="):].strip()
    except OSError:
        pass
    return None


def resolve_binary(cmd: str) -> str:
    parts = cmd.split()
    if not parts:
        return ""
    binary = parts[0]
    for prefix in ("/bin/", "/usr/bin/", "/usr/local/bin/"):
        if binary.startswith(prefix):
            return binary
    return binary if binary.startswith("/") else ""


def flag_severity(bin_path: str) -> str | None:
    if not bin_path:
        return None
    p = Path(bin_path)
    if p.is_file():
        return None if os.access(str(p), os.X_OK) else "MEDIUM"
    if shutil.which(bin_path):
        return None
    return "HIGH"


def is_ura_unit(name: str) -> bool:
    lower = name.lower()
    keywords = ["ura", "openclaw", "opencode", "tuneladora", "model-router",
                "central-router", "backend@", "gx10", "llama"]
    return any(k in lower for k in keywords)


def scan(fix: bool = False, ura_only: bool = True) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    units = collect_units()

    for scope, paths in units.items():
        for unit_path in paths:
            name = Path(unit_path).stem
            if ura_only and not is_ura_unit(name):
                continue
            cmd = extract_execstart(unit_path)
            if not cmd:
                continue
            bin_path = resolve_binary(cmd)
            severity = flag_severity(bin_path)
            if severity is None:
                continue

            unit_name = Path(unit_path).name
            entry = {
                "unit": unit_name,
                "scope": scope,
                "severity": severity,
                "execstart": cmd,
                "missing": bin_path,
                "path": unit_path,
            }
            results.append(entry)

            if fix and severity == "HIGH":
                _disable_and_delete(unit_name, scope)

    return results


def _disable_and_delete(unit: str, scope: str) -> None:
    user_flag = ["--user"] if scope == "user" else []
    try:
        subprocess.run(
            [SYSTEMCTL, *user_flag, "disable", "--now", unit],
            capture_output=True, timeout=30,
        )
    except Exception:
        pass
    for d in TIMER_DIRS:
        timer = Path(d) / unit.replace(".service", ".timer")
        if timer.exists():
            try:
                subprocess.run(
                    [SYSTEMCTL, *user_flag, "disable", "--now", timer.name],
                    capture_output=True, timeout=30,
                )
            except Exception:
                pass
            timer.unlink(missing_ok=True)
    unit_path = Path(SYSTEM_UNITS if scope == "system" else USER_UNITS) / unit
    if unit_path.exists():
        unit_path.unlink()


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    flags = set(sys.argv[1:])

    fix = "--fix" in flags
    ura_only = "--all" not in flags
    as_json = "--json" in flags

    results = scan(fix=fix, ura_only=ura_only)

    if as_json:
        import datetime
        print(json.dumps({
            "timestamp": datetime.datetime.now(UTC).isoformat(),
            "scanner": "systemd_orphan_scanner",
            "total": len(results),
            "fix": fix,
            "ura_only": ura_only,
            "results": results,
        }, indent=2))
    else:
        print(f"[systemd_orphan_scanner] Orphans found: {len(results)}")
        for r in results:
            s = r["severity"]
            icon = "🔴" if s == "HIGH" else "🟡"
            print(f"  {icon} [{s}] {r['unit']} ({r['scope']}) -> {r['missing']}")
            print(f"       {r['execstart'][:120]}")
        if fix:
            print(f"[systemd_orphan_scanner] Fixed {len(results)} units")


if __name__ == "__main__":
    main()
