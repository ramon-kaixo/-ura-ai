#!/bin/bash
# deploy_gx10.sh — Despliega fixes en GX10
# Ejecutar desde ~/URA/ura_ia_1972 en LOCAL:
# bash scripts/deploy_gx10.sh <GX10_USER>@<GX10_IP>

set -e

GX10="${1:-ramon@10.164.1.99}"
URA_REMOTE="/home/ramon/URA/ura_ia_1972"
LOCAL_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "═══════════════════════════════════════════"
echo " DESPLIEGUE URA — Fixes central_router"
echo "═══════════════════════════════════════════"
echo "Target: ${GX10}"
echo "Local:  ${LOCAL_DIR}"
echo ""

# 1. Copiar __init__.py faltantes
echo "[1/5] Copiando __init__.py faltantes..."
INIT_FILES=(
  "core/__init__.py"
  "core/buscadores/__init__.py"
  "core/code_agents/__init__.py"
  "core/code_agents/mobile/__init__.py"
  "core/code_agents/tools/__init__.py"
  "core/connectors/__init__.py"
  "core/handlers/__init__.py"
  "core/nodes/__init__.py"
  "core/services/__init__.py"
  "core/ui/__init__.py"
  "panels/__init__.py"
)

for f in "${INIT_FILES[@]}"; do
  scp "${LOCAL_DIR}/${f}" "${GX10}:${URA_REMOTE}/${f}"
  echo "  ✓ ${f}"
done

# 2. Instalar servicio systemd
echo "[2/5] Instalando servicio systemd..."
scp "${LOCAL_DIR}/central-router.service" "${GX10}:/tmp/central-router.service"
ssh "${GX10}" "sudo mv /tmp/central-router.service /etc/systemd/system/ && sudo systemctl daemon-reload"

# 3. Reiniciar servicio
echo "[3/5] Reiniciando central-router.service..."
ssh "${GX10}" "sudo systemctl restart central-router.service"

# 4. Verificar estado
echo "[4/5] Verificando estado del servicio..."
sleep 3
ssh "${GX10}" "systemctl status central-router.service --no-pager"

# 5. Diagnostics
echo "[5/5] Ejecutando diagnóstico..."
scp "${LOCAL_DIR}/scripts/diag_gx10.sh" "${GX10}:${URA_REMOTE}/scripts/"
ssh "${GX10}" "cd ${URA_REMOTE} && bash scripts/diag_gx10.sh"

echo ""
echo "═══════════════════════════════════════════"
echo " DESPLIEGUE COMPLETADO"
echo "═══════════════════════════════════════════"
echo "Logs: ssh ${GX10} 'journalctl -u central-router.service -f'"
