#!/bin/bash
set -euo pipefail
# agente_centinela.sh — Alertas en tiempo real desde Frigate via MQTT
MQTT_HOST="${MQTT_HOST:-10.164.1.99}"
MQTT_TOPIC="frigate/events"
GX10_URL="http://10.164.1.99:11434/api/chat"
MODEL="${CENTINELA_MODEL:-llama3.2-vision:11b}"
ALERT_ZONES=("almacen" "cocina_restringida")

echo "   🛡️ Centinela escuchando MQTT en $MQTT_HOST ..."

command -v mosquitto_sub &>/dev/null || { echo "⚠️  Instalar mosquitto: brew install mosquitto (Mac) o sudo apt install mosquitto-clients (GX10)"; exit 1; }

mosquitto_sub -h "$MQTT_HOST" -t "$MQTT_TOPIC" -W 60 2>/dev/null | while read -r payload; do
    [ -z "$payload" ] && continue
    CAMARA=$(echo "$payload" | jq -r '.after.camera // empty')
    LABEL=$(echo "$payload" | jq -r '.after.label // empty')
    ZONE=$(echo "$payload" | jq -r '.after.entered_zones[]? // empty')
    EVENT_ID=$(echo "$payload" | jq -r '.after.id // empty')
    [ "$LABEL" != "person" ] || [ -z "$ZONE" ] && continue

    for zona in "${ALERT_ZONES[@]}"; do
        if [ "$ZONE" = "$zona" ]; then
            echo "   ⚠️ Persona en $ZONE ($CAMARA)"
            SNAP=$(mktemp /tmp/centinela_XXXXXX.jpg)
            curl -s -o "$SNAP" "http://10.164.1.99:5000/api/${CAMARA}/latest.jpg" 2>/dev/null || { rm -f "$SNAP"; break; }
            PAYLOAD=$(python3 -c "
import json, base64
with open('$SNAP','rb') as f:
    b64 = base64.b64encode(f.read()).decode()
payload = {
    'model': '$MODEL',
    'messages': [{'role': 'user', 'content': 'Eres un vigilante. Describe en una frase que hace la persona en la zona $ZONE. Es empleado o cliente? Debo preocuparme?', 'images': [b64]}],
    'stream': False
}
print(json.dumps(payload))
")
            ANALISIS=$(echo "$PAYLOAD" | curl -s --max-time 20 -X POST "$GX10_URL" -H "Content-Type: application/json" -d @- | jq -r '.message.content // "Sin analisis"' 2>/dev/null || echo "Sin analisis")
            MSG="🚨 $ZONE ($CAMARA): $ANALISIS"
            echo "   $MSG" >> /tmp/centinela.log
            if [ -n "${TELEGRAM_BOT_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
                curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/sendMessage" \
                    -d "chat_id=${TELEGRAM_CHAT_ID}" -d "text=$MSG" >/dev/null 2>&1 || true
            fi
            rm -f "$SNAP"
            break
        fi
    done
done
echo "   Centinela detenido"
