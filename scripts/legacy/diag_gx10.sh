#!/usr/bin/env python3
"""Diagnóstico completo para central_router en GX10."""
import sys
import os
import traceback
from pathlib import Path

URA = Path(os.environ.get("URA_PATH", os.path.expanduser("~/URA/ura_ia_1972")))
sys.path.insert(0, str(URA))
sys.path.insert(0, str(URA / "core"))
sys.path.insert(0, str(URA / "agents"))

print(f"URA path: {URA}")
print(f"Existe: {URA.exists()}")

# Verificar __init__.py en todos los directorios de importación
dirs_to_check = ["core", "agents", "services", "handlers", "core/buscadores",
                 "core/code_agents", "core/code_agents/mobile", "core/code_agents/tools",
                 "core/connectors", "core/handlers", "core/nodes", "core/services", "core/ui", "panels"]

missing = []
for d in dirs_to_check:
    init = URA / d / "__init__.py"
    if not init.exists():
        missing.append(str(init))

if missing:
    print(f"\nFaltan {len(missing)} __init__.py:")
    for m in missing:
        print(f"  ✗ {m}")
else:
    print("\nTodos los __init__.py están presentes")

# Verificar servicio systemd en GX10
svc = Path("/etc/systemd/system/central-router.service")
print(f"\nServicio systemd en {svc}: {'EXISTE' if svc.exists() else 'NO EXISTE'}")

# Verificar que llama-server está disponible
llama = Path.home() / "llama.cpp/build_cuda/bin/llama-server"
print(f"llama-server: {'EXISTE' if llama.exists() else 'NO EXISTE'}")

# Verificar modelos GGUF
for name, cfg in [("codestral-22b", "models/llama-cpp/codestral-22b.gguf"),
                   ("qwen2.5-coder-q8", "models/llama-cpp/qwen2.5-coder-q8_0.gguf")]:
    p = Path.home() / cfg
    print(f"Modelo {name}: {'EXISTE' if p.exists() else 'NO EXISTE'} ({p})")

# Intentar importar central_router (el test crítico)
print("\n--- IMPORT TEST ---")
try:
    from core.central_router import CentralRouter
    r = CentralRouter()
    print(f"✓ CentralRouter OK | {r.get_status()}")
except Exception as e:
    print(f"✗ CentralRouter FAIL: {e}")
    traceback.print_exc()
