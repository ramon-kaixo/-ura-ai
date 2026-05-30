#!/bin/bash
# limpiar_nodos_ausentes.sh - Expulsa nodos ausentes mas de 7 dias
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
NODOS_DB="${REPO}/data/nodos_conocidos.json"
DIAS_UMBRAL=7

if [ ! -f "$NODOS_DB" ]; then
    echo "Base de datos de nodos no encontrada: $NODOS_DB"
    exit 0
fi

ANTES=$(jq '.nodos | length' "$NODOS_DB")
jq --arg dias "$DIAS_UMBRAL" '
    .nodos |= map(
        select(
            .last_seen == null or
            (now - ((.last_seen | fromdateiso8601?) // 0)) < ($dias | tonumber * 86400)
        )
    )
' "$NODOS_DB" > tmp.json && mv tmp.json "$NODOS_DB"

DESPUES=$(jq '.nodos | length' "$NODOS_DB")
ELIMINADOS=$((ANTES - DESPUES))
if [ "$ELIMINADOS" -gt 0 ]; then
    echo "Nodos ausentes eliminados: $ELIMINADOS"
else
    echo "No hay nodos ausentes"
fi
