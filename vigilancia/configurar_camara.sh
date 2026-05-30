#!/bin/bash
set -euo pipefail
# configurar_camara.sh — Prueba credenciales y genera entrada en frigate.yml
IP="$1"
FRIGATE_CONFIG="${HOME}/frigate/config.yml"
[ -f "$FRIGATE_CONFIG" ] && cp "$FRIGATE_CONFIG" "${FRIGATE_CONFIG}.bak.$(date +%Y%m%d_%H%M%S)"

CREDS=("admin:admin" "admin:password" "admin:12345" "user:user" "admin:" ":")
STREAM=""
echo "   🔧 Configurando $IP..."

for cred in "${CREDS[@]}"; do
    USER="${cred%%:*}"
    PASS="${cred##*:}"
    RTSP_URL="rtsp://$USER:$PASS@$IP:554/live"
    SNAP=$(mktemp /tmp/cam_test_XXXXXX.jpg)
    if ffmpeg -rtsp_transport tcp -i "$RTSP_URL" -vframes 1 -q:v 2 "$SNAP" 2>/dev/null; then
        STREAM="$RTSP_URL"
        echo "     ✅ Credenciales: $USER:***"
        rm -f "$SNAP"
        break
    fi
    rm -f "$SNAP"
done

if [ -z "$STREAM" ]; then
    echo "     ❌ Sin credenciales validas"
    exit 1
fi

CAM_NAME="cam_$(echo "$IP" | tr '.' '_')"
mkdir -p "$(dirname "$FRIGATE_CONFIG")"
cat >> "$FRIGATE_CONFIG" << EOF

  ${CAM_NAME}:
    ffmpeg:
      inputs:
        - path: $STREAM
          roles:
            - detect
            - record
    detect:
      width: 1280
      height: 720
      fps: 5
    objects:
      track:
        - person
    record:
      retain:
        days: 7
EOF

docker restart frigate 2>/dev/null || true
echo "   ✅ $CAM_NAME configurada en Frigate"
