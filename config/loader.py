"""Config loader — reads dispositivos.json and system_config.json.

Deprecation: La nueva config (core/config.py UraConfig.load()) lee
system_config.json directamente. Este módulo solo se mantiene para
dispositivos.json. Migrar a UraConfig.load() para config general."""

import json
from pathlib import Path
from typing import Any

URA_ROOT = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        with open(path) as f:  # noqa: PTH123
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return None


def get_device_ip(device_key: str, interface: str = "ip_cable") -> str | None:
    cfg = _load_json(URA_ROOT / "config" / "dispositivos.json")
    if not cfg:
        return None
    device = cfg.get("dispositivos", {}).get(device_key, {})
    return device.get(interface)


def get_device(device_key: str) -> dict[str, Any]:
    cfg = _load_json(URA_ROOT / "config" / "dispositivos.json")
    if not cfg:
        return {}
    return cfg.get("dispositivos", {}).get(device_key, {})


def get_admin_email() -> str:
    cfg = _load_json(URA_ROOT / "config" / "dispositivos.json")
    if not cfg:
        return "barkaixo@gmail.com"
    return cfg.get("admin_email", "barkaixo@gmail.com")


def get_profile(name: str = "linux_asus") -> dict[str, Any] | None:
    cfg = _load_json(URA_ROOT / "config" / "system_config.json")
    if not cfg:
        return None
    return cfg.get("profiles", {}).get(name)
