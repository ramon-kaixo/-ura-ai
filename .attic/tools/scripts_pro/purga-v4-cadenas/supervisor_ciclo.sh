#!/bin/bash
# supervisor_ciclo.sh — Ciclo del Mac Supervisor: descubre, despliega, supervisa
# Se ejecuta cada 5 minutos via crontab

LOG="/var/log/ura_supervisor.log"
NOTIFICAR="/opt/ura/scripts/notificar.sh"
REPO="${HOME}/URA/ura_ia_1972"
DISPOSITIVOS="/tmp/ura_dispositivos_activos.txt"
NUEVOS="/tmp/ura_nuevos_dispositivos.txt"
COPILOTOS="/tmp/ura_copilotos_registrados.txt"

echo "[$(date)] Supervisor ciclo iniciado" >> "$LOG"

# 1. Descubrir dispositivos y puertos
bash "$REPO/scripts/pro/descubrir_puertos.sh" >> "$LOG" 2>&1

# 2. Detectar nuevos dispositivos (comparar con lista anterior)
touch "$COPILOTOS"
while read -r ip name; do
    [ -z "$ip" ] && continue
    if ! grep -q "$ip" "$COPILOTOS" 2>/dev/null; then
        echo "$ip $name" >> "$NUEVOS"
        echo "NUEVO: $ip ($name)" >> "$LOG"
    fi
done < "$DISPOSITIVOS"

# 3. Desplegar Copiloto en cada dispositivo nuevo
if [ -f "$NUEVOS" ]; then
    while read -r ip name; do
        [ -z "$ip" ] && continue
        echo "Desplegando Copiloto en $ip ($name)..." >> "$LOG"
        # Intentar deploy
        if bash "$REPO/scripts/pro/deploy_copilotos.sh" "$name" >> "$LOG" 2>&1; then
            echo "$ip" >> "$COPILOTOS"
            [ -x "$NOTIFICAR" ] && "$NOTIFICAR" "Copiloto desplegado en $name ($ip)"
        fi
    done < "$NUEVOS"
    rm -f "$NUEVOS"
fi

# 4. Supervisar estado de todos los Copilotos
while read -r ip name; do
    [ -z "$ip" ] && continue
    # Health check via SSH (si es accesible)
    if ping -c1 -W2 "$ip" >/dev/null 2>&1; then
        echo "OK $name ($ip)" >> "$LOG"
    else
        echo "SIN RESPUESTA $name ($ip)" >> "$LOG"
        [ -x "$NOTIFICAR" ] && "$NOTIFICAR" "Copiloto en $name sin respuesta"
    fi
done < "$DISPOSITIVOS"

echo "[$(date)] Supervisor ciclo completado" >> "$LOG"
