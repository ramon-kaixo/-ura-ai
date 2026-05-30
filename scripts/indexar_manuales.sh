#!/bin/bash
# indexar_manuales.sh - Indexa manuales en ChromaDB
set -e

URA_BASE="$(cd "$(dirname "$0")/.." && pwd)"
MANUAL_DIR="$URA_BASE/docs/manuales"
PY_INDEXER="$URA_BASE/core/memory/indexar_manuales.py"

mkdir -p "$URA_BASE/core/memory"

cat > "$PY_INDEXER" << 'PYEOF'
import os
import sys

ura_base = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ura_base)

from core.memory.semantic_brain import SemanticBrain

brain = SemanticBrain()
manual_dir = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ura_base, "docs", "manuales")

if not os.path.exists(manual_dir):
    print(f"Directorio de manuales no encontrado: {manual_dir}")
    sys.exit(1)

for filename in os.listdir(manual_dir):
    if not filename.endswith(".txt"):
        continue
    app_name = filename.replace(".txt", "")
    path = os.path.join(manual_dir, filename)
    with open(path, "r") as f:
        content = f.read()
    secciones = content.split("\n## ")
    for i, sec in enumerate(secciones):
        if i == 0 and not sec.startswith("##"):
            sec = sec.lstrip("#").strip()
        else:
            sec = sec.strip()
        if sec:
            brain.indexar_manual(app_name, sec, f"seccion_{i}")
    print(f"Indexado {filename}")
PYEOF

source "$URA_BASE/.venv/bin/activate" 2>/dev/null || true
python3 "$PY_INDEXER" "$MANUAL_DIR"
