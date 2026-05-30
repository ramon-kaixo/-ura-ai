#!/usr/bin/env python3
"""
Diagnóstico de crash de central_router en GX10.
Ejecutar en GX10: python3 ~/URA/ura_ia_1972/scripts/diagnose_central_router.py
"""

import sys
import traceback

print("=" * 60)
print("DIAGNÓSTICO CENTRAL ROUTER")
print("=" * 60)

# 1. Verificar Python
print(f"\n[1] Python: {sys.version}")
print(f"    Path: {sys.executable}")

# 2. Verificar directorio de trabajo
import os

cwd = os.getcwd()
print(f"\n[2] CWD: {cwd}")
ura_path = os.path.expanduser("~/URA/ura_ia_1972")
if os.path.isdir(ura_path):
    print(f"    URA path existe: {ura_path}")
else:
    print(f"    ERROR: URA path NO existe: {ura_path}")

# 3. Verificar sys.path
print("\n[3] sys.path:")
for p in sys.path:
    print(f"    {p}")

# 4. Verificar PYTHONPATH
env_pythonpath = os.environ.get("PYTHONPATH", "(no definido)")
print(f"\n[4] PYTHONPATH: {env_pythonpath}")

if URA_PATH := os.path.expanduser("~/URA/ura_ia_1972"):
    if URA_PATH not in sys.path:
        sys.path.insert(0, URA_PATH)
        print(f"    → Añadido {URA_PATH} a sys.path")

# 5. Verificar imports críticos
print("\n[5] Probando imports...")
modules_to_test = [
    ("core.shared_memory", "SharedMemory"),
    ("core.forensic_scribe", "ForensicScribe"),
    ("core.unified_logger", "UnifiedLogger"),
    ("core.intent_detector", "IntentDetector"),
    ("core.degradation_manager", "DegradationManager"),
    ("core.agent_metadata", "AgentMetadata"),
    ("core.observability", "Observability"),
    ("core.ura_diary", "URAdiary"),
    ("core.timeout_manager", "get_timeout_manager"),
]

for mod_name, sym in modules_to_test:
    try:
        mod = __import__(mod_name, fromlist=[sym])
        print(f"    ✓ {mod_name}")
    except Exception as e:
        print(f"    ✗ {mod_name} → {e}")

# 6. Verificar archivo de servicio systemd
service_path = "/etc/systemd/system/central-router.service"
print(f"\n[6] Servicio systemd: {service_path}")
if os.path.exists(service_path):
    with open(service_path) as f:
        print(f"    Contenido:\n{f.read()}")
else:
    print(f"    ERROR: Archivo de servicio NO existe en {service_path}")
    # Buscar en home
    home_service = os.path.expanduser("~/URA/ura_ia_1972/central-router.service")
    if os.path.exists(home_service):
        print(f"    Encontrado en: {home_service}")
    else:
        print("    No se encontró en ningún sitio")

# 7. Intentar importar central_router
print("\n[7] Importando central_router...")
try:
    from core.central_router import CentralRouter

    print("    ✓ CentralRouter importado exitosamente")

    # 8. Intentar instanciar
    print("\n[8] Instanciando CentralRouter()...")
    router = CentralRouter()
    print("    ✓ Router instanciado")
    print(f"    Status: {router.get_status()}")
except Exception as e:
    print(f"    ✗ ERROR: {e}")
    traceback.print_exc()

print("\n" + "=" * 60)
print("FIN DEL DIAGNÓSTICO")
print("=" * 60)
