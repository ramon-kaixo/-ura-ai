#!/bin/bash
# rotate_secrets.sh — Rotación automática de secrets URA
# 
# Este script:
#   1. Comprueba si los secrets tienen más de 90 días
#   2. Si es necesario rotar, notifica al administrador
#   3. Provee instrucciones para cada plataforma
#
# Uso: ./rotate_secrets.sh [--check|--notify]

set -euo pipefail

SECRETS_FILE="/etc/ura/secrets.env"
ROTATION_LOG="/home/ramon/URA/backups/reports/secret_rotation.json"
MAX_AGE_DAYS="${1:-90}"

check_rotation_needed() {
    if [ ! -f "$ROTATION_LOG" ]; then
        echo '{"last_rotation": null, "next_rotation": null}' > "$ROTATION_LOG"
    fi
    
    local last_rotation
    last_rotation=$(python3 -c "import json; d=json.load(open('$ROTATION_LOG')); print(d.get('last_rotation',''))")
    
    if [ -z "$last_rotation" ]; then
        echo "Nunca se ha rotado. Rotación necesaria."
        return 0
    fi
    
    local last_ts
    last_ts=$(date -d "$last_rotation" +%s)
    local now
    now=$(date +%s)
    local days_elapsed=$(( (now - last_ts) / 86400 ))
    
    if [ "$days_elapsed" -ge "$MAX_AGE_DAYS" ]; then
        echo "Última rotación hace $days_elapsed días (límite: $MAX_AGE_DAYS). Rotación necesaria."
        return 0
    fi
    
    echo "OK: $days_elapsed días desde última rotación (límite: $MAX_AGE_DAYS)"
    return 1
}

show_instructions() {
    cat << 'EOF'
=== INSTRUCCIONES DE ROTACIÓN ===

1. OPENROUTER_API_KEY
   Ir a: https://openrouter.ai/keys
   Generar nueva key y actualizar en /etc/ura/secrets.env

2. DEEPSEEK_API_KEY
   Ir a: https://platform.deepseek.com/api_keys
   Generar nueva key y actualizar

3. GEMINI_API_KEY
   Ir a: https://aistudio.google.com/app/apikey
   Generar nueva key y actualizar

4. TELEGRAM_TOKEN
   Ir a: https://t.me/BotFather
   Revocar token actual y generar nuevo

5. PUSHOVER_*
   Ir a: https://pushover.net/apps
   Generar nuevo token de aplicación

6. LANGFUSE_SECRET_KEY
   Ir a: https://langfuse.com
   Generar nuevo par de keys

7. URA_TOKEN / URA_API_KEY
   Elegir nuevo valor aleatorio:
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"

Después de rotar, ejecutar:
   sudo systemctl daemon-reload
   sudo systemctl restart ura-ejecutor model-router ura-detector

Y actualizar:
   /home/ramon/URA/ura_ia_1972/.env.secrets.template
EOF
}

notify() {
    local msg="Rotación de secrets necesaria (última hace >$MAX_AGE_DAYS días)"
    python3 -c "
from core.notifier import notify
notify('$msg', level='warning')
" 2>/dev/null || echo "Notificación falló (notifier no disponible)"
}

# === Main ===
MODE="${1:---check}"

case "$MODE" in
    --check)
        if check_rotation_needed; then
            show_instructions
            notify
        fi
        ;;
    --notify)
        notify
        ;;
    --done)
        # Marcamos rotación como completada
        python3 -c "
import json, datetime
with open('$ROTATION_LOG') as f: d = json.load(f)
d['last_rotation'] = datetime.datetime.utcnow().isoformat()
d['next_rotation'] = (datetime.datetime.utcnow() + datetime.timedelta(days=$MAX_AGE_DAYS)).isoformat()
with open('$ROTATION_LOG', 'w') as f: json.dump(d, f, indent=2)
"
        echo "Rotación registrada. Próxima rotación: $(python3 -c "import json; print(json.load(open('$ROTATION_LOG'))['next_rotation'])")"
        ;;
    *)
        echo "Uso: $0 [--check|--notify|--done]"
        exit 1
        ;;
esac
