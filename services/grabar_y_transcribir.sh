#!/bin/bash
# grabar_y_transcribir.sh
# Captura audio + Whisper-large-v3 con sistema de aceptacion/rechazo

WHISPER_URL="http://gx10-ts:8090/transcribe"
DATOS_VOZ="$HOME/URA/ura_ia_1972/data/voz"
AUDIO_DIR="$DATOS_VOZ/grabaciones"
SESIONES_DIR="$DATOS_VOZ/sesiones"
mkdir -p "$AUDIO_DIR" "$SESIONES_DIR"

SESION_ID=$(date +%Y%m%d_%H%M%S)
SESION_FILE="$SESIONES_DIR/sesion_${SESION_ID}.json"

echo "{\"sesion_id\": \"$SESION_ID\", \"timestamp\": \"$(date -Iseconds)\", \"intentos\": []" > "$SESION_FILE"

INTENTO=0
ACEPTADO=""

while true; do
    INTENTO=$((INTENTO + 1))
    AUDIO_FILE="$AUDIO_DIR/sesion_${SESION_ID}_intento_${INTENTO}.wav"
    
    echo ""
    echo "════════════════════════════════════════"
    echo "🎤 INTENTO #$INTENTO — Pulsa ENTER para grabar"
    echo "════════════════════════════════════════"
    read
    
    echo "🔴 Grabando... Pulsa Ctrl+C cuando termines."
    sox -d -r 16000 -c 1 -b 16 "$AUDIO_FILE" 2>/dev/null &
    SOX_PID=$!
    
    trap "kill $SOX_PID 2>/dev/null" INT
    wait $SOX_PID 2>/dev/null
    trap - INT
    
    if [ ! -s "$AUDIO_FILE" ]; then
        echo "❌ No se grabo nada."
        rm -f "$AUDIO_FILE"
        INTENTO=$((INTENTO - 1))
        continue
    fi
    
    DURACION=$(sox "$AUDIO_FILE" -n stat 2>&1 | grep "Length" | awk '{print $3}')
    TAMANO=$(du -h "$AUDIO_FILE" | cut -f1)
    echo ""
    echo "✅ Grabado: $TAMANO ($DURACION s)"
    echo "📡 Enviando a Whisper..."
    
    RESPUESTA=$(USUARIO="${URA_USUARIO:-ramon}"
    curl -s -X POST "$WHISPER_URL" -F "audio=@$AUDIO_FILE" -F "usuario=$USUARIO")
    TEXTO=$(echo "$RESPUESTA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('text', 'ERROR'))" 2>/dev/null)
    TEXTORAW=$(echo "$RESPUESTA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('text_raw', ''))" 2>/dev/null)
    CORR=$(echo "$RESPUESTA" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('corrections_applied', 0))" 2>/dev/null)
    
    if [ -z "$TEXTO" ] || [ "$TEXTO" = "ERROR" ]; then
        echo "❌ Error en transcripcion."
        continue
    fi
    
    echo ""
    echo "────────────────────────────────────────"
    echo "📝 TRANSCRIPCION #$INTENTO ($CORR correcciones):"
    echo "────────────────────────────────────────"
    echo "$TEXTO"
    echo "────────────────────────────────────────"
    echo ""
    echo "[a] Aceptar  [r] Repetir  [s] Salir"
    echo -n "→ "
    read -n 1 DECISION
    echo ""
    
    case "$DECISION" in
        a|A)
            ACEPTADO="$AUDIO_FILE"
            echo "✅ Aceptado"
            echo "$TEXTO" | pbcopy
            echo "📋 Copiado al portapapeles"
            echo "💾 Sesion: $SESION_FILE"
            break
            ;;
        s|S)
            echo "🚫 Salir. Audios guardados, ninguno aceptado."
            exit 0
            ;;
        *)
            echo "🔄 Repitiendo..."
            ;;
    esac
done

echo ""
echo "🎙  Sesion #$SESION_ID — $INTENTO intento(s)"
