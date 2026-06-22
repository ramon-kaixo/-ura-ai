#!/bin/bash
# deploy_mac.sh — Espera a que Mac Mini esté online y despliega ura-motor
# Uso: ./deploy_mac.sh          # un solo intento
#      ./deploy_mac.sh --watch  # loop cada 5 min hasta que responda

MAC_HOST="mini-de-ramon"
MAC_USER="ramon"
MOTOR_DIR="/home/ramon/URA/ura_ia_1972/motor"
REMOTE_DIR="/opt/motor"

deploy() {
    echo "[$(date '+%H:%M:%S')] Mac Mini online — desplegando..."
    scp -r "$MOTOR_DIR" "${MAC_USER}@${MAC_HOST}:/tmp/" || return 1
    ssh "${MAC_USER}@${MAC_HOST}" "sudo rm -rf $REMOTE_DIR && sudo cp -r /tmp/motor $REMOTE_DIR && sudo ln -sf $REMOTE_DIR/scripts/ura /usr/local/bin/ura-motor && sudo mkdir -p /etc/ura && echo '{\"deploy_dir\":\"$REMOTE_DIR/deploy\",\"data_dir\":\"$REMOTE_DIR/data\",\"qdrant_host\":\"100.72.103.12\",\"qdrant_port\":6333}' | sudo tee /etc/ura/config.json && sudo $REMOTE_DIR/scripts/ura pipeline" 2>&1
    echo "OK" || echo "FAIL"
}

ping -c 1 -W 3 "$MAC_HOST" &>/dev/null && deploy || {
    echo "Mac Mini offline"
    [ "$1" == "--watch" ] && while true; do
        sleep 300
        ping -c 1 -W 3 "$MAC_HOST" &>/dev/null && deploy && break
    done
}
