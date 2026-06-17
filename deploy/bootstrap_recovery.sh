#!/bin/bash
# ============================================================
# bootstrap_recovery.sh — Recovery + Blindaje para ASUS GX10
# Ejecutar DESPUÉS de restaurar SSH en ASUS.
# Uso: ssh ramon@10.164.1.99 'bash -s' < deploy/bootstrap_recovery.sh
# ============================================================
set -euo pipefail
REPO="${ASUS_PATH:-/home/ramon/URA}/ura_ia_1972"
cd "$REPO"

echo "=== [1/6] Kill procesos hambrientos ==="
sudo pkill -f "docker pull" 2>/dev/null || true
ps aux --sort=-%mem 2>/dev/null | awk '$4>50 {print $2}' | xargs -r sudo kill -9 2>/dev/null || true
df -h

echo "=== [2/6] Desplegar jaulas de recursos ==="
sudo bash scripts/pro/jaulas_recursos.sh

echo "=== [3/6] Instalar dropbear :2222 ==="
sudo apt-get install -y dropbear 2>/dev/null || true
sudo sed -i 's/DROPBEAR_PORT=22/DROPBEAR_PORT=2222/' /etc/default/dropbear 2>/dev/null || true
sudo systemctl restart dropbear 2>/dev/null || true
sudo systemctl enable dropbear 2>/dev/null || true

echo "=== [4/6] Instalar monitoreo urgente (crontab) ==="
echo '* * * * * bash /home/ramon/URA/ura_ia_1972/scripts/pro/monitoreo_urgente.sh' | sudo crontab -

echo "=== [5/6] Arrancar Qdrant + seed ==="
sudo systemctl daemon-reload
sudo systemctl enable --now qdrant 2>/dev/null || true
echo "Esperando Qdrant..."
for i in $(seq 1 30); do
    if curl -sf http://localhost:6333/health >/dev/null 2>&1; then
        echo "Qdrant OK"
        break
    fi
    sleep 2
done
python3 scripts/seed_transacciones.py

echo "=== [6/6] Reactivar servicios ==="
sudo systemctl restart ura-executor 2>/dev/null || true

echo "========================================="
echo "Recovery + Blindaje completado."
echo "  Qdrant: systemctl status qdrant"
echo "  ura-executor: systemctl status ura-executor"
echo "  Dropbear: ssh -p 2222 ramon@localhost"
echo "  Seed: transacciones en ura_transacciones"
echo "========================================="
