#!/bin/bash
# Test de Arena de Mejora Continua - Verifica todas las herramientas

set -euo pipefail

echo "🧪 Test de Arena de Mejora Continua"
echo "======================================"

ERRORS=0

# Test 1: shellcheck
echo ""
echo "🔍 Test shellcheck..."
if command -v shellcheck &>/dev/null; then
    echo "✅ shellcheck instalado: $(shellcheck --version)"
else
    echo "❌ shellcheck no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 2: hadolint
echo ""
echo "🔍 Test hadolint..."
if command -v hadolint &>/dev/null; then
    echo "✅ hadolint instalado: $(hadolint --version)"
else
    echo "❌ hadolint no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 3: yamllint
echo ""
echo "🔍 Test yamllint..."
if command -v yamllint &>/dev/null; then
    echo "✅ yamllint instalado: $(yamllint --version)"
else
    echo "❌ yamllint no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 4: trivy
echo ""
echo "🔍 Test trivy..."
if command -v trivy &>/dev/null; then
    echo "✅ trivy instalado: $(trivy --version)"
else
    echo "❌ trivy no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 5: mypy
echo ""
echo "🔍 Test mypy..."
if command -v mypy &>/dev/null; then
    echo "✅ mypy instalado: $(mypy --version)"
else
    echo "❌ mypy no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 6: pytest-cov
echo ""
echo "🔍 Test pytest-cov..."
if python3 -c "import pytest_cov" &>/dev/null; then
    echo "✅ pytest-cov instalado"
else
    echo "❌ pytest-cov no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 7: coverage
echo ""
echo "🔍 Test coverage..."
if command -v coverage &>/dev/null; then
    echo "✅ coverage instalado: $(coverage --version)"
else
    echo "❌ coverage no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 8: jscpd (npm, no instalado en Arena Python)
echo ""
echo "ℹ️  jscpd es npm, no instalado en Arena Python"

# Test 9: trufflehog (npm, no instalado en Arena Python)
echo ""
echo "ℹ️  trufflehog es npm, no instalado en Arena Python"

# Test 10: semgrep
echo ""
echo "🔍 Test semgrep..."
if command -v semgrep &>/dev/null; then
    echo "✅ semgrep instalado: $(semgrep --version)"
else
    echo "❌ semgrep no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 11: uv
echo ""
echo "🔍 Test uv..."
if command -v uv &>/dev/null; then
    echo "✅ uv instalado: $(uv --version)"
else
    echo "❌ uv no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 12: pre-commit
echo ""
echo "🔍 Test pre-commit..."
if command -v pre-commit &>/dev/null; then
    echo "✅ pre-commit instalado: $(pre-commit --version)"
else
    echo "❌ pre-commit no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 13: memray
echo ""
echo "🔍 Test memray..."
if command -v memray &>/dev/null; then
    echo "✅ memray instalado: $(memray --version)"
else
    echo "❌ memray no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Test 14: py-spy
echo ""
echo "🔍 Test py-spy..."
if command -v py-spy &>/dev/null; then
    echo "✅ py-spy instalado: $(py-spy --version)"
else
    echo "❌ py-spy no instalado"
    ERRORS=$((ERRORS + 1))
fi

# Resumen
echo ""
echo "======================================"
if [[ $ERRORS -eq 0 ]]; then
    echo "✅ Todas las herramientas instaladas"
    exit 0
else
    echo "❌ $ERRORS herramientas faltan"
    exit 1
fi
