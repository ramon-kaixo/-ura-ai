#!/bin/bash
# Proteger la rama main en GitHub mediante API.
# Requiere: gh CLI instalado y autenticado (gh auth login)
set -e

if ! command -v gh &>/dev/null; then
    echo "❌ GitHub CLI no instalado. Ejecuta: brew install gh"
    exit 1
fi

gh auth status &>/dev/null || {
    echo "🔑 No autenticado. Ejecutando gh auth login..."
    gh auth login
}

REPO=$(gh repo view --json nameWithOwner -q .nameWithOwner 2>/dev/null || echo "")
if [ -z "$REPO" ]; then
    echo "❌ No se pudo determinar el repositorio. ¿Estás dentro del directorio del repo?"
    exit 1
fi

echo "🔒 Protegiendo rama main en $REPO ..."
gh api "repos/$REPO/branches/main/protection" \
    --method PUT \
    --field required_status_checks='{"strict":true,"contexts":["ci"]}' \
    --field enforce_admins=true \
    --field required_pull_request_reviews='{"required_approving_review_count":1}' \
    --field restrictions=null && echo "✅ Rama main protegida" || echo "⚠️  No se pudo proteger (puede que ya lo esté)"
