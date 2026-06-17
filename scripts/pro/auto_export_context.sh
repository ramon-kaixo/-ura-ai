#!/usr/bin/env bash
# auto_export_context.sh — Export ura_context.json to Hetzner backup.
# Called by cron every 30 minutes.
# Uses /tmp copy to avoid race condition with concurrent writes.
set -euo pipefail

HETZNER_MAGICDNS="${HETZNER_MAGICDNS:-hetzner-node.tail-net.ts.net}"
HETZNER_SSH_PORT="${HETZNER_SSH_PORT:-2222}"
HETZNER_USER="${HETZNER_USER:-ramon}"
HETZNER_PATH="${HETZNER_PATH:-/backups/ura_context.json}"
CONTEXT_SRC="${HOME}/.config/opencode/ura_context.json"
CONTEXT_TMP="/tmp/ura_context.export"

# Only run if endpoint resolves
if ! host "$HETZNER_MAGICDNS" >/dev/null 2>&1; then
    exit 0
fi

# Copy to temp to avoid race condition with concurrent writes
cp "$CONTEXT_SRC" "$CONTEXT_TMP"

rsync -e "ssh -p ${HETZNER_SSH_PORT} -o ConnectTimeout=10" \
    "$CONTEXT_TMP" \
    "${HETZNER_USER}@${HETZNER_MAGICDNS}:${HETZNER_PATH}" 2>/dev/null || true
