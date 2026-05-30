# Sistema de seguridad permanente del GX10

> **Fecha:** 2026-05-12
> **Estado:** Diseño. NO implementado.
> **Propósito:** Guardián 24/7 que protege el hardware automáticamente.

---

## 1. Propósito

Daemon que vigila el GX10 24/7 y actúa automáticamente para protegerlo. No es para tests puntuales — está **SIEMPRE** activo, desde el arranque hasta el apagado.

---

## 2. Umbrales de seguridad

### 2.1 Críticos (acción inmediata)

| Métrica | Umbral STOP | Acción |
|---|---|---|
| Temperatura GPU | > 86°C | Pausar todo, esperar enfriar a < 70°C |
| GPU sostenido | > 96% por > 30 min | Reducir lote a la mitad permanentemente |
| VRAM usada | > 92% | Liberar modelos no esenciales (ollama stop) |
| RAM sistema | > 95% | Pausar todas las tareas no críticas |
| Swap usado | > 10 GB | Alerta Pushover + pausar tareas nuevas |

### 2.2 Warning (ajuste suave)

| Métrica | Umbral | Acción |
|---|---|---|
| Temperatura | 75-85°C | Reducir lote según tabla de abajo |
| GPU | 90-96% | Mantener observación, no acción inmediata |
| VRAM | 85-90% | No cargar más modelos |

---

## 3. Tabla de reducción de lote por temperatura

| Temperatura | Tamaño paquete | Pausa entre items |
|---|---|---|
| < 65°C | 100% (base) | 0s |
| 65-70°C | 75% | 1s |
| 70-75°C | 50% | 2s |
| 75-80°C | 25% | 5s |
| 80-85°C | 10% | 10s |
| > 85°C | PAUSA | Espera enfriar a < 70°C |

**Fórmula del batch_factor:**
```bash
if   temp < 65 → batch_factor = 1.00
elif temp < 70 → batch_factor = 0.75
elif temp < 75 → batch_factor = 0.50
elif temp < 80 → batch_factor = 0.25
elif temp < 85 → batch_factor = 0.10
else           → batch_factor = 0.00  (PAUSA)
```

---

## 4. Daemon — `guardian_gx10.sh`

Corre como servicio systemd, arranca con el sistema. Lee métricas cada 10 segundos.

### Código completo

```bash
#!/bin/bash
# guardian_gx10.sh — Guardián permanente del GX10
# systemd: /etc/systemd/system/guardian-gx10.service

CONFIG_DIR=~/.config/limites
STATE_FILE=~/.ura/guardian_estado.json
ALERTA_COOLDOWN=300  # 5 min entre alertas Pushover

mkdir -p "$CONFIG_DIR" ~/.ura
LAST_ALERT=0
HIGH_GPU_SINCE=0

while true; do
    # ── Leer métricas ──
    read TEMP GPU_UTIL VRAM_USED VRAM_TOTAL <<< $(nvidia-smi \
        --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total \
        --format=csv,noheader,nounits 2>/dev/null | tr ',' ' ')
    TEMP=${TEMP:-0}; GPU_UTIL=${GPU_UTIL:-0}
    VRAM_USED=${VRAM_USED:-0}; VRAM_TOTAL=${VRAM_TOTAL:-1024}

    RAM_TOTAL=$(free -g | awk '/^Mem:/ {print $2}')
    RAM_USED=$(free -g | awk '/^Mem:/ {print $3}')
    RAM_PCT=$(( RAM_USED * 100 / RAM_TOTAL ))
    VRAM_PCT=$(( VRAM_USED * 100 / VRAM_TOTAL ))
    SWAP_USED=$(free -g | awk '/^Swap:/ {print $3}')

    LOAD=$(uptime | awk -F'load average:' '{print $2}' | cut -d, -f1 | tr -d ' ')

    # ── Calcular batch_factor por temperatura ──
    if [ "$TEMP" -gt 85 ]; then
        BATCH_FACTOR=0.00; ACCION="pausa_termica"
    elif [ "$TEMP" -gt 80 ]; then
        BATCH_FACTOR=0.10; ACCION="reduciendo_lote"
    elif [ "$TEMP" -gt 75 ]; then
        BATCH_FACTOR=0.25; ACCION="reduciendo_lote"
    elif [ "$TEMP" -gt 70 ]; then
        BATCH_FACTOR=0.50; ACCION="reduciendo_lote"
    elif [ "$TEMP" -gt 65 ]; then
        BATCH_FACTOR=0.75; ACCION="normal"
    else
        BATCH_FACTOR=1.00; ACCION="normal"
    fi

    # ── Comprobar críticos ──
    ALERTA=""
    NOW=$(date +%s)

    # Temperatura crítica
    if [ "$TEMP" -gt 86 ]; then
        touch "$CONFIG_DIR/PAUSA_GLOBAL"
        ALERTA="Temperatura critica: ${TEMP}°C"
    else
        rm -f "$CONFIG_DIR/PAUSA_GLOBAL"
    fi

    # GPU sostenido > 96% por más de 30 min
    if [ "$GPU_UTIL" -gt 96 ]; then
        if [ "$HIGH_GPU_SINCE" -eq 0 ]; then
            HIGH_GPU_SINCE=$NOW
        elif [ $((NOW - HIGH_GPU_SINCE)) -gt 1800 ]; then
            BATCH_FACTOR=$(echo "scale=2; $BATCH_FACTOR * 0.5" | bc)
            ALERTA="$ALERTA GPU >96% por 30min. Lote reducido a la mitad."
            HIGH_GPU_SINCE=0
        fi
    else
        HIGH_GPU_SINCE=0
    fi

    # VRAM crítica
    if [ "$VRAM_PCT" -gt 92 ]; then
        ALERTA="$ALERTA VRAM al ${VRAM_PCT}%"
    fi

    # RAM crítica
    if [ "$RAM_PCT" -gt 95 ]; then
        touch "$CONFIG_DIR/PAUSA_GLOBAL"
        ALERTA="$ALERTA RAM al ${RAM_PCT}%"
    fi

    # Swap excesivo
    if [ "$SWAP_USED" -gt 10 ]; then
        ALERTA="$ALERTA Swap alto: ${SWAP_USED}GB"
    fi

    # ── Escribir estado ──
    echo "{\"temp\":$TEMP,\"gpu\":$GPU_UTIL,\"vram_pct\":$VRAM_PCT,\"ram_pct\":$RAM_PCT,\"swap_gb\":$SWAP_USED,\"load\":$LOAD,\"batch_factor\":$BATCH_FACTOR,\"accion\":\"$ACCION\",\"ts\":$NOW}" > "$STATE_FILE"
    echo "$BATCH_FACTOR" > "$CONFIG_DIR/batch_factor"

    # ── Alerta Pushover (con cooldown) ──
    if [ -n "$ALERTA" ] && [ $((NOW - LAST_ALERT)) -gt $ALERTA_COOLDOWN ]; then
        curl -s --max-time 5 -X POST https://api.pushover.net/1/messages.json \
            -d token="${PUSHOVER_APP_TOKEN}" \
            -d user="${PUSHOVER_USER_KEY}" \
            -d title="GX10 ALERTA" \
            -d message="$ALERTA" \
            -d priority=1 2>/dev/null || true
        LAST_ALERT=$NOW
    fi

    sleep 10
done
```

---

## 5. Cómo las tareas obedecen al guardián

Cualquier script de tarea pesada (Kimi-audit, benchmark, etc.) consulta antes de cada lote:

```bash
# 1. ¿Pausa global?
if [ -f ~/.config/limites/PAUSA_GLOBAL ]; then
    echo "PAUSA_GLOBAL activa — esperando 30s..."
    sleep 30
    continue
fi

# 2. ¿Factor de lote?
BATCH_FACTOR=$(cat ~/.config/limites/batch_factor 2>/dev/null || echo "1.0")
BATCH_SIZE=$(echo "$BATCH_BASE * $BATCH_FACTOR / 1" | bc)
[ "$BATCH_SIZE" -lt 1 ] && BATCH_SIZE=1

# 3. ¿Pausa entre items?
if [ "$(echo "$BATCH_FACTOR < 0.25" | bc)" -eq 1 ]; then
    sleep 5  # pausa extra entre archivos
fi
```

**Flujo completo:**

```
guardian_gx10.sh (cada 10s)
    │
    ├── PAUSA_GLOBAL    ← si temp > 86°C o RAM > 95%
    ├── batch_factor    ← 0.0 a 1.0 según temperatura
    └── guardian_estado.json ← snapshot completo
        │
        ▼
kimi_review_limpio.sh (antes de cada lote)
    │
    ├── ¿PAUSA_GLOBAL? → sleep 30, reintentar
    ├── batch_factor   → ajustar BATCH_SIZE
    └── procesar lote
```

---

## 6. Instalación como servicio systemd

```ini
# /etc/systemd/system/guardian-gx10.service
[Unit]
Description=Guardian de seguridad GX10
After=multi-user.target

[Service]
Type=simple
User=ramon
ExecStart=/home/ramon/bin/guardian_gx10.sh
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable guardian-gx10
sudo systemctl start guardian-gx10
sudo systemctl status guardian-gx10
```

---

## 7. Prueba del guardián

### Simular temperatura alta (sin riesgo real)

```bash
# Forzar batch_factor a 0.10 (simula 80°C)
echo "0.10" > ~/.config/limites/batch_factor

# Forzar pausa global
touch ~/.config/limites/PAUSA_GLOBAL

# Verificar que las tareas obedecen
cat ~/.config/limites/batch_factor
# Debe devolver 0.10

# Limpiar después de la prueba
rm ~/.config/limites/PAUSA_GLOBAL
echo "1.0" > ~/.config/limites/batch_factor
```

---

## 8. Monitorización humana

```bash
# Estado en tiempo real
watch -n 2 cat ~/.ura/guardian_estado.json

# Última alerta
tail -1 ~/.ura/guardian_alerts.log

# Batch factor actual
cat ~/.config/limites/batch_factor

# Historial de temperatura (últimas 100 líneas)
tail -100 ~/logs/metricas_gx10.csv | awk -F',' '{print $3}' | sort -rn | head -5
```

---

## 9. Integración con dosificador universal

El guardián es el **nivel 0** (hardware) del sistema de protección:

```
Nivel 0: guardian_gx10.sh      ← protección del hardware (SIEMPRE)
Nivel 1: controlador_recursos.sh ← dosificador de tareas (cuando hay carga)
Nivel 2: auditoria_resiliente.sh ← reinicios preventivos (auditorías largas)
```

Cada nivel es independiente pero se complementan:
- Guardián para emergencias de hardware
- Controlador para ajuste fino de carga
- Auditoría resiliente para trabajos muy largos

---

## 10. Estado actual

| Componente | Estado |
|---|---|
| `guardian_gx10.sh` | Diseñado, no implementado |
| systemd unit | No creado |
| `PAUSA_GLOBAL` | Usado por controlador_recursos.sh |
| `batch_factor` | Usado por controlador_recursos.sh |
| Integración con auditoría | En diseño |
| Métricas reales: temp | 61-63°C en 5h al 96% GPU — muy seguro |
