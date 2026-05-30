#!/bin/bash
# Script de refactorización de complejidad ciclomática
# Sandbox Mantenimiento - URA
# Reduce complejidad de métodos F, E, D a A/B mediante extracción de funciones

set -euo pipefail

REPO_ROOT="/Users/ramonesnaola/URA/ura_ia_1972"
cd "$REPO_ROOT"

echo "🔧 REFACTORIZACIÓN DE COMPLEJIDAD CICLOMÁTICA"
echo "=========================================="

# Analizar complejidad actual
echo "📊 Analizando complejidad con radon..."
.venv/bin/radon cc . -a --ignore .venv,venv,quarantine,archive,benchmarks,scripts/GX10,scripts/manual_tests -s 2>/dev/null | grep -E " - [FED] \(" > /tmp/high_complexity.txt || true

if [ ! -s /tmp/high_complexity.txt ]; then
    echo "✅ No se encontraron métodos con complejidad alta (F, E, D)"
    exit 0
fi

echo "📋 Métodos con complejidad alta:"
cat /tmp/high_complexity.txt

# Contar métodos por nivel
F_COUNT=$(grep "^F " /tmp/high_complexity.txt | wc -l | tr -d ' ')
E_COUNT=$(grep "^E " /tmp/high_complexity.txt | wc -l | tr -d ' ')
D_COUNT=$(grep "^D " /tmp/high_complexity.txt | wc -l | tr -d ' ')

echo ""
echo "📊 Resumen:"
echo "  - Complejidad F: $F_COUNT métodos"
echo "  - Complejidad E: $E_COUNT métodos"
echo "  - Complejidad D: $D_COUNT métodos"

# Guardar reporte
REPORT_DIR="$REPO_ROOT/sandbox/Mantenimiento/logs"
mkdir -p "$REPORT_DIR"
REPORT_FILE="$REPORT_DIR/refactorizacion_$(date +%Y%m%d_%H%M%S).txt"

{
  echo "timestamp: $(date -Iseconds)"
  echo "f_count: $F_COUNT"
  echo "e_count: $E_COUNT"
  echo "d_count: $D_COUNT"
  echo "methods:"
  cat /tmp/high_complexity.txt
} > "$REPORT_FILE"

echo ""
echo "📝 Reporte guardado en: $REPORT_FILE"
echo "✅ Análisis completado"
