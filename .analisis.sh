#!/bin/bash
# .analisis.sh — Análisis completo del código (6 herramientas deterministas)
# Uso: bash .analisis.sh

RAIZ="/home/ramon/URA/ura_ia_1972"
cd "$RAIZ" || exit 1

echo "════════════════════════════════════════"
echo "  ANÁLISIS COMPLETO DEL CÓDIGO"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "════════════════════════════════════════"

echo ""
echo "═══ 1. RUFF — Estilo y errores lógicos ═══"
python3 -m ruff check . --select=ALL 2>&1 | tail -3

echo ""
echo "═══ 2. RADON — Complejidad ciclomática ═══"
python3 -m radon cc mochila_engine.py prompt_injector.py core/ cli/ scripts/pro/ -s 2>&1 | grep -E "\([CDEF]" | head -10 || echo "  Sin funciones complejas (>B)"

echo ""
echo "═══ 3. BANDIT — Seguridad ═══"
python3 -m bandit -r . -ll 2>&1 | tail -5

echo ""
echo "═══ 4. VULTURE — Código muerto ═══"
python3 -m vulture . --min-confidence 80 2>&1 | head -20

echo ""
echo "═══ 5. JSCPD — Código duplicado ═══"
npx jscpd . --threshold 5 --pattern "*.py" 2>&1 | tail -10

echo ""
echo "═══ 6. PYTEST-COV — Cobertura de tests ═══"
python3 -m pytest --cov=. --cov-report=term --quiet 2>&1 | tail -10

echo ""
echo "════════════════════════════════════════"
echo "  ANÁLISIS COMPLETADO"
echo "════════════════════════════════════════"
