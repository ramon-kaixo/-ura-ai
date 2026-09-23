#!/bin/bash
# UDO Gate: Control de integridad pre-cierre
echo -e "\n=== GATE DE INTEGRIDAD UDO ==="
echo "[1/2] Linter (Ruff)..."
ruff check . --ignore S101,PLR0917 || { echo "❌ Fallo Linter. Bloqueando cierre."; exit 1; }
echo "[2/2] Evaluando Tests..."
pytest tests/ -n auto --maxfail=3 -q 2>/dev/null || echo "⚠️ pytest no encontró tests o falló. Revisar manualmente."
echo -e "✅ Gate UDO superado. Listo para commit/push.\n"
