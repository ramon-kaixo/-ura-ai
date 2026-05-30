#!/bin/bash
# scripts/sensor_recursos.sh — Devuelve retardo en segundos segun RAM libre
# Uso: DELAY=$(bash scripts/sensor_recursos.sh)
# Retorna 0.5, 1, 2 o 3 segundos segun carga del sistema
FREE_MB=$(vm_stat | awk '/free/ {print $3}' | sed 's/\.//')
TOTAL_MB=$(sysctl hw.memsize | awk '{print $2/1024/1024}')
USED_PCT=$(echo "scale=0; 100 - ($FREE_MB * 4096 / $TOTAL_MB)" | bc)

if   [ "$USED_PCT" -lt 30 ]; then echo 0.5
elif [ "$USED_PCT" -lt 50 ]; then echo 1
elif [ "$USED_PCT" -lt 70 ]; then echo 2
else echo 3
fi
