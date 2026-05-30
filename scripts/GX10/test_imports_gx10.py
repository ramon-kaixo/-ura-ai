#!/usr/bin/env python3
"""Test de imports criticos en GX10."""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "core")

modules = [
    "core.shared_memory",
    "core.forensic_scribe",
    "core.unified_logger",
    "core.intent_detector",
    "core.degradation_manager",
    "core.agent_metadata",
    "core.observability",
    "core.ura_diary",
    "core.timeout_manager",
    "core.ura_config",
]

ok = 0
fail = 0
for m in modules:
    try:
        __import__(m)
        print(f"  OK {m}")
        ok += 1
    except Exception as e:
        print(f"  FAIL {m}: {e}")
        fail += 1

print(f"\n{ok} OK, {fail} FAIL de {len(modules)}")
if fail > 0:
    sys.exit(1)
