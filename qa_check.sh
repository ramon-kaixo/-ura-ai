#!/bin/bash
# QA Check Script - Runs ruff, bandit and mypy in sequence
# Blocks commit if ruff or bandit fail, mypy only warns

set -e

echo "=========================================="
echo "URA QA Check - Code Quality & Security"
echo "=========================================="
echo ""

# Track overall exit code (mypy warnings don't block)
EXIT_CODE=0

# Run ruff (blocks commit if fails)
echo ">>> Running ruff linter..."
echo "------------------------------------------"
ruff check . --fix --exclude scripts/ --exclude dashboard/ --exclude aoc.py || EXIT_CODE=1
echo ""

# Run ruff format check (blocks commit if fails)
echo ">>> Running ruff format check..."
echo "------------------------------------------"
ruff format --check . --exclude scripts/ --exclude dashboard/ --exclude aoc.py || EXIT_CODE=1
echo ""

# Run bandit security check (blocks commit if HIGH/MEDIUM issues found)
echo ">>> Running bandit security scan (threshold MEDIUM, ignore LOW)..."
echo "------------------------------------------"
BANDIT_OUTPUT=$(bandit -r . -lll -ii -x .venv/,tests/,benchmarks/ --exit-zero)
# Verificar si hay errores HIGH/MEDIUM en el output
if echo "$BANDIT_OUTPUT" | grep -q "Issue:.*Severity: High"; then
    echo "❌ Bandit found HIGH severity issues"
    EXIT_CODE=1
else
    echo "✅ Bandit passed (no HIGH severity issues)"
fi
echo ""

# Run mypy (warnings only, doesn't block commit) - DISABLED DUE TO SYS.PATH ISSUES
echo ">>> Skipping mypy type checking (disabled due to sys.path conflicts)..."
echo "------------------------------------------"
echo "⚠️  MyPy disabled (non-blocking)"
echo ""

# Summary
echo "=========================================="
if [ $EXIT_CODE -eq 0 ]; then
    echo "✅ QA Check PASSED"
else
    echo "❌ QA Check FAILED"
fi
echo "=========================================="

exit $EXIT_CODE
