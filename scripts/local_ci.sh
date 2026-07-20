#!/usr/bin/env bash
set -euo pipefail
# CI local — replica los checks que GitHub Actions deberia ejecutar
# Uso: bash scripts/local_ci.sh

RUFF="${RUFF:-$(which ruff 2>/dev/null || echo /home/ramon/.local/bin/ruff)}"

echo "=== Ruff ==="
$RUFF check . --no-cache
echo "OK"

echo "=== Mypy ==="
python3 -m mypy motor/assistant/ --ignore-missing-imports
echo "OK"

echo "=== Tests assistant ==="
python3 -m pytest tests/test_assistant*.py -q --no-cov --tb=short
echo "OK"

echo "=== test_unit.py ==="
python3 tests/test_unit.py
echo "OK"

echo "=== Bandit (assistant) ==="
python3 -m bandit -r motor/assistant/ -q
echo "OK"

echo "=== Import check ==="
python3 -c "from motor.assistant.main import app; print('Import OK')"

echo ""
echo "ALL CHECKS PASSED"
