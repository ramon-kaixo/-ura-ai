#!/bin/bash
set -e
MOTOR_DIR="/opt/motor"
PYTHON="python3"

echo "=== URA Motor de Conocimiento - Instalacion ==="

SRC_DIR="$(dirname "$(readlink -f "$0")")"
SRC_DIR="$(dirname "$SRC_DIR")"
if [ "$SRC_DIR" != "$MOTOR_DIR" ]; then
    cp -r "$SRC_DIR"/* "$MOTOR_DIR/"
fi
chmod +x "$MOTOR_DIR/scripts/ura"
ln -sf "$MOTOR_DIR/scripts/ura" /usr/local/bin/ura

$PYTHON -m pip install --quiet psutil qdrant_client 2>/dev/null || true

if command -v apt-get &>/dev/null; then
    apt-get install -y -qq smartmontools lm-sensors 2>/dev/null || true
fi

mkdir -p /etc/ura
if [ ! -f /etc/ura/config.json ]; then
    cat > /etc/ura/config.json << 'CFG'
{
  "deploy_dir": "/opt/motor/deploy",
  "data_dir": "/opt/motor/data",
  "failure_knowledge_path": "/opt/motor/data/failure_knowledge_inicial.json",
  "baseline_path": "/opt/motor/data/baseline_inicial.json"
}
CFG
fi

cat > /etc/systemd/system/ura-pipeline.service << 'EOF'
[Unit]
Description=URA Motor de Conocimiento - Pipeline completo
After=network.target qdrant.service

[Service]
Type=oneshot
ExecStart=/usr/local/bin/ura --config /etc/ura/config.json pipeline
Environment=URA_CONFIG=/etc/ura/config.json
User=root
StandardOutput=journal
StandardError=journal
EOF

cat > /etc/systemd/system/ura-pipeline.timer << 'EOF'
[Unit]
Description=URA Pipeline cada 5 minutos
Requires=ura-pipeline.service

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
EOF

systemctl daemon-reload
systemctl disable --now ura-hetzner-watchdog.timer 2>/dev/null || true
systemctl disable --now ura-scanner.timer 2>/dev/null || true
systemctl disable --now ura-diagnostico.timer 2>/dev/null || true
systemctl enable --now ura-pipeline.timer || true

echo "OK. ura pipeline cada 5 min activo."
echo "  ura pipeline      # ejecutar ahora"
echo "  ura status        # estado unificado"
echo "  ura check         # preflight"
echo "  ura scan          # solo escanear"
echo "  ura diagnose      # solo diagnosticar"
echo "  ura history       # incidentes Qdrant"
echo "  ura calibrate     # generar baseline"
