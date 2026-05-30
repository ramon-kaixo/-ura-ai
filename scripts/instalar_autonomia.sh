#!/bin/bash
# instalar_autonomia.sh - Instala los timers launchd para autonomia URA
set -euo pipefail

REPO="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"

echo "========================================="
echo "  URA - Instalacion de Autonomia"
echo "  $(date)"
echo "========================================="

mkdir -p "$PLIST_DIR"

# 1. Timer principal del enjambre (cada 15 min)
echo ""
echo "[1/5] Instalando timer del enjambre..."
cat > "$PLIST_DIR/com.ura.enjambre.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.enjambre</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/orquestador/bibliotecario.sh</string>
    </array>
    <key>StartInterval</key>
    <integer>900</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_enjambre.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_enjambre_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.enjambre.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.enjambre.plist"
echo "   ✅ Enjambre cada 15 min"

# 2. Timer de autonomia avanzada (cada 5 min)
echo ""
echo "[2/5] Instalando timer de autonomia..."
cat > "$PLIST_DIR/com.ura.autonomia.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.autonomia</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>${REPO}/agents/autonomia_avanzada.py</string>
    </array>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/tmp/ura_autonomia.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_autonomia_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.autonomia.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.autonomia.plist"
echo "   ✅ Autonomia cada 5 min"

# 3. Timer de indexacion multimodal (diario 02:00)
echo ""
echo "[3/5] Instalando timer de indexacion..."
cat > "$PLIST_DIR/com.ura.indexacion.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.indexacion</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/scripts/indexar_manuales_multimodal.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ura_indexacion.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_indexacion_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.indexacion.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.indexacion.plist"
echo "   ✅ Indexacion diaria 02:00"

# 4. Timer de anonimizacion (diario 04:00)
echo ""
echo "[4/5] Instalando timer de anonimizacion..."
cat > "$PLIST_DIR/com.ura.anonimizacion.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.anonimizacion</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>${REPO}/scripts/anonymize_data.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>4</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ura_anonimizacion.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_anonimizacion_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.anonimizacion.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.anonimizacion.plist"
echo "   ✅ Anonimizacion diaria 04:00"

# 5. Timer de fine-tune vision (semanal domingo 03:00)
echo ""
echo "[5/5] Instalando timer de fine-tune vision..."
cat > "$PLIST_DIR/com.ura.vision_finetune.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.vision_finetune</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/scripts/auto_finetune_vision.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
        <key>Weekday</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ura_vision_finetune.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_vision_finetune_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.vision_finetune.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.vision_finetune.plist"
echo "   ✅ Fine-tune vision semanal domingo 03:00"

# 6. Timer de mock TPV (si no hay TPV real)
echo ""
echo "[6/7] Instalando timer de mock TPV..."
cat > "$PLIST_DIR/com.ura.mocktpv.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.mocktpv</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>${REPO}/scripts/mock_tpv_api.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${REPO}</string>
    <key>StandardOutPath</key>
    <string>/tmp/mock_tpv.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/mock_tpv_error.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.mocktpv.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.mocktpv.plist"
echo "   ✅ Mock TPV siempre activo"

# 7. Timer de TPV Spy (lector pasivo de Access DB)
echo ""
echo "[7/8] Instalando timer de TPV Spy..."
cat > "$PLIST_DIR/com.ura.tpvsyp.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.tpvsyp</string>
    <key>ProgramArguments</key>
    <array>
        <string>python3</string>
        <string>${REPO}/scripts/tpv_spy.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>${REPO}</string>
    <key>StandardOutPath</key>
    <string>/tmp/ura_tpv_spy.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_tpv_spy_error.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.tpvsyp.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.tpvsyp.plist"
echo "   ✅ TPV Spy activo (lectura pasiva Access DB)"

# 8. Timer de backup de config (diario 03:00)
echo ""
echo "[8/8] Instalando timer de backup de config..."
cat > "$PLIST_DIR/com.ura.backup_config.plist" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.ura.backup_config</string>
    <key>ProgramArguments</key>
    <array>
        <string>bash</string>
        <string>${REPO}/scripts/backup_config.sh</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>/tmp/ura_backup_config.log</string>
    <key>StandardErrorPath</key>
    <string>/tmp/ura_backup_config_err.log</string>
</dict>
</plist>
EOF
launchctl unload "$PLIST_DIR/com.ura.backup_config.plist" 2>/dev/null || true
launchctl load "$PLIST_DIR/com.ura.backup_config.plist"
echo "   ✅ Backup config diario 03:00"

# Resumen
echo ""
echo "========================================="
echo "  Timers instalados"
echo "========================================="
echo ""
launchctl list | grep com.ura
echo ""
echo "Logs:"
echo "  Enjambre:      tail -f /tmp/ura_enjambre.log"
echo "  Autonomia:     tail -f /tmp/ura_autonomia.log"
echo "  Indexacion:    tail -f /tmp/ura_indexacion.log"
echo "  Anonimizacion: tail -f /tmp/ura_anonimizacion.log"
echo "  Vision:        tail -f /tmp/ura_vision_finetune.log"
echo "  Mock TPV:      tail -f /tmp/mock_tpv.log"
echo "  Backup Config: tail -f /tmp/ura_backup_config.log"
