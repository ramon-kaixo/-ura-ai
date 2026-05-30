#!/bin/bash
set -euo pipefail
PROVIDER="${1:-}"
ACTION="${2:-create}"
[ -z "$PROVIDER" ] && { echo "Uso: deploy.sh <aws|azure|gcp> [--destroy]"; exit 1; }
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
case "$PROVIDER" in
    aws)   source "${SCRIPT_DIR}/providers/aws_credentials.sh" 2>/dev/null || true
           source "${SCRIPT_DIR}/providers/aws.sh" ;;
    azure) source "${SCRIPT_DIR}/providers/azure_credentials.sh" 2>/dev/null || true
           source "${SCRIPT_DIR}/providers/azure.sh" ;;
    gcp)   source "${SCRIPT_DIR}/providers/gcp_credentials.sh" 2>/dev/null || true
           source "${SCRIPT_DIR}/providers/gcp.sh" ;;
    *)     echo "Proveedor no soportado: $PROVIDER"; exit 1 ;;
esac
if [ "$ACTION" = "--destroy" ]; then
    INSTANCE_ID=$(cat "${SCRIPT_DIR}/.instance_id" 2>/dev/null || echo "")
    [ -z "$INSTANCE_ID" ] && echo "🔴 No hay instancia activa" && exit 1
    destroy_instance "$INSTANCE_ID"
    rm -f "${SCRIPT_DIR}/.instance_id"
else
    create_instance "${2:-t3.medium}" "${3:-us-east-1}" "${4:-ura-cloud}"
fi
