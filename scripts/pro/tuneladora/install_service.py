"""Instala el servicio systemd de la tuneladora."""
from __future__ import annotations

import shutil
import subprocess  # nosec B404
from pathlib import Path


def install_service(user: str = "ramon") -> dict[str, str | bool]:
    import os as _os2

    if _os2.geteuid() != 0:
        return {"error": "Se necesita sudo para instalar servicio", "ok": False}

    repo = Path(__file__).resolve().parent.parent.parent.parent
    src = repo / "deploy" / "ura-tuneladora.service"
    dst = Path("/etc/systemd/system/ura-tuneladora.service")
    results: dict[str, str | bool] = {}

    if not src.exists():
        return {"error": f"Service file no encontrado: {src}", "ok": False}

    try:
        shutil.copy2(str(src), str(dst))
        results["copy"] = "ok"
    except PermissionError:
        results["copy"] = "denied (need sudo)"
        return {**results, "ok": False}

    for cmd, name in [
        (["systemctl", "daemon-reload"], "daemon-reload"),
        (["systemctl", "enable", "ura-tuneladora"], "enable"),
        (["systemctl", "start", "ura-tuneladora"], "start"),
    ]:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, check=False)  # nosec B603 B607
        results[name] = "ok" if r.returncode == 0 else r.stderr[:100]

    r = subprocess.run(["systemctl", "status", "ura-tuneladora"], capture_output=True, text=True, timeout=10, check=False)  # nosec B603 B607
    results["status"] = "active" if "active" in r.stdout else "inactive"
    results["ok"] = results.get("start") == "ok"

    return results


if __name__ == "__main__":
    import json
    result = install_service()
    print(json.dumps(result, indent=2))
