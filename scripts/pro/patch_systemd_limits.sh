#!/usr/bin/env bash
# patch_systemd_limits.sh — Inyección automatizada de directivas de control de pánico
# en las unidades de servicio systemd para evitar el agotamiento de CPU por reinicios
# en bucle infinito (100ms).
#
# Uso: sudo bash scripts/pro/patch_systemd_limits.sh

SERVICES_DIR="/etc/systemd/system"
TARGET_SERVICES=(
    "ura-voice.service" "ura-xvfb.service" "opencode.service"
    "snc.service" "ollama.service" "qdrant.service" "model-router.service"
)

# Capturar también servicios dinámicos docker-ura
mapfile -t DOCKER_SERVICES < <(ls $SERVICES_DIR/docker-ura-*.service 2>/dev/null)

for svc_path in "${TARGET_SERVICES[@]}" "${DOCKER_SERVICES[@]}"; do
    full_path="$SERVICES_DIR/$svc_path"
    if [ -f "$full_path" ]; then
        echo "[+] Aplicando Rate-Limit a: $svc_path"
        # Remover duplicados previos si existen
        sed -i '/StartLimitIntervalSec/d' "$full_path"
        sed -i '/StartLimitBurst/d' "$full_path"
        sed -i '/RestartSec/d' "$full_path"

        # Inyectar bajo la sección [Service]
        sed -i '/\[Service\]/a StartLimitIntervalSec=60\nStartLimitBurst=3\nRestartSec=10' "$full_path"
    fi
done

systemctl daemon-reload
echo "[*] Unidades Systemd securizadas con éxito."
