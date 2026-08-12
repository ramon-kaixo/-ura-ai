#!/usr/bin/env bash
# Hook semgrep para pre-commit: usa el semgrep del venv y redirige
# caches a ${TMPDIR:-/tmp} (rootfs RO en ASUS: ~/.cache y ~/.semgrep
# no son escribibles desde el entorno de trabajo).
# Uso (pre-commit): entry: 'scripts/pro/run_semgrep_hook.sh'
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE="${TMPDIR:-/tmp}/opencode"

export XDG_CONFIG_HOME="${XDG_CONFIG_HOME:-$BASE/xdg}"
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$BASE/xdg-cache}"
export SEMGREP_SETTINGS_FILE="${SEMGREP_SETTINGS_FILE:-$BASE/semgrep-settings.yml}"
export SEMGREP_LOG_FILE="${SEMGREP_LOG_FILE:-$BASE/semgrep.log}"

mkdir -p "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME"
exec "$REPO/.venv/bin/semgrep" --config="$REPO/.semgrep.yml" --quiet "$@"