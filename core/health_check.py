#!/usr/bin/env python3
"""
End-to-End Health Check — URA
Verifica que todos los componentes del sistema estén funcionando.
"""

import sys
from pathlib import Path

import psutil
import requests

PROJECT = Path("/Users/ramonesnaola/URA/ura_ia_1972")
CHECKS = []


def check(name: str, fn, critical: bool = True) -> bool:
    try:
        result = fn()
        status = "✅" if result else "❌"
        print(f"  {status} {name}")
        if critical and not result:
            CHECKS.append(f"CRÍTICO: {name} falló")
        return result
    except Exception as e:
        print(f"  ❌ {name}: {e}")
        if critical:
            CHECKS.append(f"CRÍTICO: {name}: {e}")
        return False


print("=" * 50)
print("  URA HEALTH CHECK")
print("=" * 50)
print()

# 1. Ollama
print("[Ollama]")
check(
    "Ollama responde :11434",
    lambda: requests.get("http://localhost:11434/api/tags", timeout=5).status_code == 200,
)
check(
    "Modelos cargados",
    lambda: (
        len(requests.get("http://localhost:11434/api/tags", timeout=5).json().get("models", []))
        >= 3
    ),
)

# 2. Dashboard
print("\n[Dashboard]")
check(
    "Dashboard :5051", lambda: requests.get("http://localhost:5051/", timeout=5).status_code == 200
)
check(
    "Métricas :5051/metrics",
    lambda: requests.get("http://localhost:5051/metrics", timeout=5).status_code == 200,
)
check(
    "Token auth funciona",
    lambda: "error" not in requests.post("http://localhost:5051/token", timeout=5).json(),
    critical=False,
)

# 3. Procesos
print("\n[Procesos]")
check(
    "Max Research corriendo",
    lambda: any(
        "max_research" in (p.info["name"] or "")
        or "max_research" in " ".join(p.info.get("cmdline", []) or [])
        for p in psutil.process_iter(["name", "cmdline"])
        if p.info["name"] and "python" in p.info["name"]
    ),
    critical=False,
)
check(
    "URA Web corriendo",
    lambda: any(
        "ura_web.py" in " ".join(p.info.get("cmdline", []) or [])
        for p in psutil.process_iter(["cmdline"])
        if p.info.get("cmdline")
    ),
    critical=False,
)

# 4. Disco
print("\n[Disco]")
disk = psutil.disk_usage("/")
disk_ok = disk.percent < 90
check(
    f"Disco {disk.percent:.0f}% usado ({disk.free / 1024**3:.0f} GB libre)",
    lambda: disk.percent < 90,
)

# 5. RAM
ram = psutil.virtual_memory()
ram_ok = ram.percent < 95
check(
    f"RAM {ram.percent:.0f}% usado ({ram.available / 1024**3:.1f} GB libre)",
    lambda: ram.percent < 95,
    critical=False,
)

# 6. Archivos del proyecto
print("\n[Proyecto]")
check("main_final.py existe", lambda: (PROJECT / "main_final.py").exists())
check(".venv existe", lambda: (PROJECT / ".venv").exists())
check("requirements.txt existe", lambda: (PROJECT / "requirements.txt").exists())

# 7. Toshiba (si está montado)
toshi = Path("/Volumes/TOSHIBA_NUEVO")
if toshi.exists():
    print("\n[Toshiba]")
    toshi_free = psutil.disk_usage(str(toshi)).free
    check(f"Toshiba montado ({toshi_free / 1024**3:.0f} GB libre)", lambda: True)

# 8. Resumen
print("\n" + "=" * 50)
if CHECKS:
    print(f"⚠️  {len(CHECKS)} problemas:")
    for c in CHECKS:
        print(f"  - {c}")
    sys.exit(1)
else:
    print("✅ TODOS LOS CHECKS PASADOS")
    sys.exit(0)
