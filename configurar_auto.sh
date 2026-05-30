#!/bin/bash
set -e

echo "🚀 Configuración automática de URA - Fase final"

# 1. Proteger rama main (requiere GitHub CLI instalado y autenticado)
if ! command -v gh &> /dev/null; then
    echo "Instalando GitHub CLI..."
    brew install gh
fi
if gh auth status &> /dev/null; then
    echo "Protegiendo rama main..."
    REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
    if [ -n "$REPO" ]; then
        gh api repos/$REPO/branches/main/protection \
          --method PUT \
          --field required_status_checks='{"strict":true,"contexts":["ci"]}' \
          --field enforce_admins=true \
          --field required_pull_request_reviews='{"required_approving_review_count":1}' || echo "⚠️ Ya protegida o error"
    fi
else
    echo "⚠️ gh no autenticado. Ejecuta 'gh auth login' y vuelve a ejecutar este script."
fi

# 2. Configurar mypy.ini extendido (solo directorios existentes)
MYPY_SECTIONS="[mypy-core.*]\nignore_errors = False\ndisallow_untyped_defs = True\n\n[mypy-agents.*]\nignore_errors = False\ndisallow_untyped_defs = True\n"
if [ -d "scripts" ]; then
    MYPY_SECTIONS="$MYPY_SECTIONS\n\n[mypy-scripts.*]\nignore_errors = False\ndisallow_untyped_defs = True\n"
fi

cat > mypy.ini << MYPYEOF
[mypy]
ignore_missing_imports = True
warn_return_any = False
disallow_untyped_defs = False

$(echo -e "$MYPY_SECTIONS")
MYPYEOF

echo "✅ mypy.ini actualizado"

# 3. Actualizar pre-commit para incluir mypy en los directorios habilitados
MYPY_DIRS="core/ agents/"
if [ -d "scripts" ]; then
    MYPY_DIRS="$MYPY_DIRS scripts/"
fi

# Buscar la línea de args del hook mypy y reemplazarla
if grep -q "mypy" .pre-commit-config.yaml; then
    if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "/- id: mypy/,/args:/ s|args: \[.*\]|args: [--follow-imports=silent, --ignore-missing-imports, $MYPY_DIRS]|" .pre-commit-config.yaml
    else
        sed -i "/- id: mypy/,/args:/ s|args: \[.*\]|args: [--follow-imports=silent, --ignore-missing-imports, $MYPY_DIRS]|" .pre-commit-config.yaml
    fi
    echo "✅ .pre-commit-config.yaml actualizado (mypy: $MYPY_DIRS)"
else
    echo "⚠️ No se encontró el hook mypy en .pre-commit-config.yaml"
fi

# 4. Instalar pytest-cov si no está
if ! python3 -c "import pytest_cov" 2>/dev/null; then
    echo "Instalando pytest-cov..."
    pip install pytest-cov --break-system-packages 2>/dev/null || pip3 install pytest-cov --break-system-packages 2>/dev/null || true
fi

# 5. Verificar cobertura (solo si pytest-cov se instaló)
if python3 -c "import pytest_cov" 2>/dev/null; then
    echo "Ejecutando tests con cobertura..."
    python3 -m pytest tests/test_core_basics.py tests/test_core_data.py tests/test_core_security.py \
      --cov=core --cov-report=term -q --maxfail=1 2>/dev/null || true
fi

echo ""
echo "✅ Configuración automática completada."
echo "📌 Recuerda:"
echo "   1. Crear el proyecto en SonarCloud (sonarcloud.io)"
echo "   2. Añadir SONAR_TOKEN como secreto: gh secret set SONAR_TOKEN --body \"tu_token\""
echo "   3. Hacer commit y push de los cambios"
