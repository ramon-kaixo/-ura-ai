#!/bin/bash
set -euo pipefail
F1="/tmp/phase1_files.txt"; F2="/tmp/phase2_files.txt"
echo "" > "$F1"
find "${HOME}/URA/ura_ia_1972" -name "*.py" -not -path "*/.venv/*" -not -path "*/quarantine/*" > "$F2"
echo "✅ Sin conflictos: Fase 1 es solo lectura"
