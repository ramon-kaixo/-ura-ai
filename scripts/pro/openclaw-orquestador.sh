#!/bin/bash
# OpenClaw — Perfil ORQUESTADOR (GX10) — wrapper con HOME virtual
# =============================================================
# El home real de ASUS está montado RO (rootfs); el CLI de OpenClaw
# necesita escribir estado (~/.openclaw-<perfil>/). Este wrapper usa un
# HOME virtual dentro del repo (/home/ramon/URA/ura_ia_1972/.openclaw-orq-home,
# partición rw) para que el perfil funcione sin sudo.
#
# Uso:
#   openclaw-orquestador.sh <comando openclaw...>
#   openclaw-orquestador.sh doctor
#   openclaw-orquestador.sh agent --local --timeout 120 --agent main -m "..."
#   openclaw-orquestador.sh exec-policy show
#
# Perfil: gateway.port=18791, gateway.bind=loopback, modelo ollama/deepseek-r1:14b
# Seguridad: exec-policy deny-all + allowlist read-only (git log/cat/grep/...)
# El gateway NO se instala como servicio (sin systemd): usar embedded --local
# o decidir instalación explícita con: openclaw-orquestador.sh gateway install
set -euo pipefail
export HOME=/home/ramon/URA/ura_ia_1972/.openclaw-orq-home
exec openclaw --profile orquestador "$@"
