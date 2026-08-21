"""Layer 0: Environment Health — disk, RAM, CPU, Ollama, processes."""

from __future__ import annotations

import logging
import os
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests

from scripts.pro.tuneladora.pipeline.runner import _free_disk_gb

log = logging.getLogger("shadow.layer0")
_requests_session = threading.local()


def _session() -> requests.Session:
    if not hasattr(_requests_session, "s"):
        _requests_session.s = requests.Session()
    return _requests_session.s


@dataclass
class EnvCheck:
    name: str
    status: str  # OK / WARN / FAIL
    detail: str = ""
    duration_ms: float = 0.0


def _get_cpu_count() -> int:
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


def _get_ram_info() -> dict[str, Any]:
    info: dict[str, Any] = {"total_mb": 0, "available_mb": 0, "percent": 0}
    try:
        import psutil

        vm = psutil.virtual_memory()
        info["total_mb"] = vm.total // (1024 * 1024)
        info["available_mb"] = vm.available // (1024 * 1024)
        info["percent"] = vm.percent
    except ImportError:
        try:
            total = 0
            available = 0
            with Path("/proc/meminfo").open() as f:
                for line in f:
                    if "MemAvailable" in line:
                        available = int(line.split()[1]) // 1024
                    elif "MemTotal" in line:
                        total = int(line.split()[1]) // 1024
            info["total_mb"] = total
            info["available_mb"] = available
            info["percent"] = round((1 - available / total) * 100, 1) if total else 0
        except Exception:
            info["available_mb"] = 2048
    return info


def _ollama_check(ollama_url: str) -> tuple[bool, int]:
    try:
        s = _session()
        r = s.get(f"{ollama_url}/api/tags", timeout=5)
        if r.status_code == 200:
            models = r.json().get("models", [])
            return True, len(models)
        return False, 0
    except Exception:
        return False, 0


def _git_available(ura_root: Path) -> bool:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-dir"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
            cwd=str(ura_root),
        )
        return r.returncode == 0
    except Exception:
        return False


def _disk_io_ok(path: Path) -> bool:
    test = path / ".shadow_health_write_test"
    try:
        test.write_text("ok")
        test.unlink()
        return True
    except Exception:
        return False


def run(ura_root: Path, ollama_url: str = "http://localhost:11434") -> list[EnvCheck]:
    results: list[EnvCheck] = []

    t0 = time.monotonic()
    free_gb = _free_disk_gb(ura_root)
    if free_gb is None:
        results.append(EnvCheck("disk", "WARN", "Could not determine disk space"))
    elif free_gb < 1:
        results.append(EnvCheck("disk", "FAIL", f"Only {free_gb:.1f} GB free"))
    else:
        results.append(EnvCheck("disk", "OK", f"{free_gb:.1f} GB free"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    ram = _get_ram_info()
    if ram["percent"] > 95:
        results.append(EnvCheck("ram", "FAIL", f"{ram['percent']}% used"))
    elif ram["percent"] > 85:
        results.append(EnvCheck("ram", "WARN", f"{ram['percent']}% used"))
    else:
        results.append(EnvCheck("ram", "OK", f"{ram['percent']}% used, {ram['available_mb']} MB free"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    ollama_ok, n_models = _ollama_check(ollama_url)
    if ollama_ok:
        results.append(EnvCheck("ollama", "OK", f"{n_models} models loaded"))
    else:
        results.append(EnvCheck("ollama", "WARN", "Ollama not responding (degraded OK)"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    n_cpu = _get_cpu_count()
    results.append(EnvCheck("cpu", "OK", f"{n_cpu} cores"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    if _git_available(ura_root):
        results.append(EnvCheck("git", "OK", "Repository available"))
    else:
        results.append(EnvCheck("git", "FAIL", "Not a git repository"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    t0 = time.monotonic()
    if _disk_io_ok(ura_root):
        results.append(EnvCheck("disk_io", "OK", "Filesystem writable"))
    else:
        results.append(EnvCheck("disk_io", "WARN", "Filesystem read-only (expected on GX10)"))
    results[-1].duration_ms = (time.monotonic() - t0) * 1000

    return results
