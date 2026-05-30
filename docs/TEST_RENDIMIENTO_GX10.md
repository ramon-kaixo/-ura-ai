# Test de rendimiento del GX10

> **Fecha:** 2026-05-12
> **Hardware:** ASUS GX10, 121 GB RAM, NVIDIA GB10 (124 GB VRAM compartida)
> **Referencia real:** Auditoría Kimi-Dev — 5h30min continuas, GPU 96%, 63°C estable

---

## 1. Rendimiento observado (datos reales)

| Métrica | CPU (`-ngl 0`) | GPU (`-ngl 80`) | Mejora |
|---|---|---|---|
| Prompt processing | 1.0 tok/s | 75.8 tok/s | 76x |
| Token generation | 1.0 tok/s | 2.7 tok/s | 2.7x |
| Tiempo por archivo (500 tok) | 8.7 min | 2.8 min | 3x |
| 268 archivos core | 39 horas | 13 horas | 3x |
| GPU temperatura | N/A | 63°C estable | — |
| GPU utilización | 0% | 96% | — |
| CPU utilización | 90%+ | 13% | — |
| RAM usada | 73 GB (host) | 86 GB (host+GPU) | — |
| VRAM usada | 1.8 GB | 71.6 GB | — |

---

## 2. Sistema de protección a 2 niveles

### Nivel 1 — Reducción adaptativa de paquete (suave)

Si el sistema se calienta o se carga mucho, NO parar el trabajo: reducir el tamaño del paquete que se procesa. El `controlador_recursos.sh` ajusta cada 10 segundos.

**Umbrales térmicos:**

| Temperatura GPU | Tamaño paquete | Reducción |
|---|---|---|
| < 65°C | 100% (base) | Ninguna |
| 65-70°C | 75% | -25% |
| 70-75°C | 50% | -50% |
| 75-80°C | 25% | -75% |
| > 80°C | PAUSA | Espera 60s, reintenta |

**Umbrales de VRAM/RAM:**

| VRAM usada | Reducción |
|---|---|
| < 80% | 0% |
| 80-90% | -50% |
| > 90% | PAUSA |

**Dato real:** Tras 5h30min de auditoría continua al 96% GPU, la temperatura se mantuvo en 63°C — muy por debajo del primer umbral. La GB10 tiene excelente refrigeración.

### Nivel 2 — Reinicio preventivo cada 25% (duro)

Cada vez que el trabajo llegue al 25%, 50% y 75% completado:

1. Guardar checkpoint (ya implementado)
2. `sudo shutdown -h now`
3. Esperar 60 segundos (enfría hardware)
4. Encender remoto (Wake-on-LAN)
5. Esperar arranque completo (~2-3 min)
6. Cargar modelo necesario (3-5 min para Kimi 72B)
7. Reanudar desde checkpoint

**Ventajas:**
- Limpia memoria fragmentada (evita leaks acumulados)
- Mata procesos zombi
- Recarga drivers CUDA/GPU
- Enfría hardware (previene throttling acumulativo)
- Aprovecha checkpoint existente (sin pérdida de trabajo)

**Coste estimado por reinicio:**

| Fase | Tiempo |
|---|---|
| Apagado | ~30s |
| Enfriado | 60s |
| Arranque + SSH | ~2-3 min |
| Carga modelo 72B | 4-5 min |
| **Total** | **~7-9 min** |

**Para una auditoría de 13h:**
- 3 reinicios (25%, 50%, 75%)
- Tiempo total perdido: 21-27 min (3.4% del total)
- Beneficio: sistema fresco cada 3-4 horas, sin degradación

---

## 3. Implementación — `auditoria_resiliente.sh`

```bash
#!/bin/bash
# auditoria_resiliente.sh — Auditoría con protección térmica + reinicios cada 25%
# Usa checkpoint.txt para reanudar tras cada reinicio

TOTAL=$(wc -l < lista_archivos.txt 2>/dev/null || echo "268")
CHECKPOINT_FILE=~/logs/kimi_review/checkpoint.txt
META_25=$((TOTAL / 4))
META_50=$((TOTAL / 2))
META_75=$((TOTAL * 3 / 4))

reiniciar() {
    local procesados=$1
    echo "[$(date)] Reinicio preventivo en $procesados/$TOTAL"
    curl -s -X POST https://api.pushover.net/1/messages.json \
        -d token="${PUSHOVER_APP_TOKEN}" \
        -d user="${PUSHOVER_USER_KEY}" \
        -d title="GX10 Reinicio" \
        -d message="Reinicio preventivo ${procesados}/${TOTAL}" \
        -d priority=0 2>/dev/null || true
    sudo shutdown -h now
    exit 0  # Cron programado encenderá en 60s
}

ajustar_batch_por_temp() {
    local temp=$(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader 2>/dev/null || echo "0")
    if [ "$temp" -gt 80 ]; then
        echo "PAUSA_TÉRMICA"
    elif [ "$temp" -gt 75 ]; then
        echo "2"
    elif [ "$temp" -gt 70 ]; then
        echo "5"
    elif [ "$temp" -gt 65 ]; then
        echo "8"
    else
        echo "10"
    fi
}

while true; do
    PROCESADOS=$(wc -l < "$CHECKPOINT_FILE" 2>/dev/null || echo "0")

    # ¿Completado?
    if [ "$PROCESADOS" -ge "$TOTAL" ]; then
        echo "[$(date)] Auditoría completada: $PROCESADOS/$TOTAL"
        break
    fi

    # ¿Reinicio preventivo?
    if [ "$PROCESADOS" -eq "$META_25" ] || \
       [ "$PROCESADOS" -eq "$META_50" ] || \
       [ "$PROCESADOS" -eq "$META_75" ]; then
        reiniciar "$PROCESADOS"
    fi

    # Ajuste térmico
    BATCH=$(ajustar_batch_por_temp)
    if [ "$BATCH" = "PAUSA_TÉRMICA" ]; then
        echo "[$(date)] PAUSA: GPU a $(nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader)°C"
        sleep 60
        continue
    fi

    # Procesar lote
    procesar_siguiente_lote "$BATCH"
done
```

---

## 4. Wake-on-LAN para reanudación

### Requisitos en GX10
1. Habilitar WOL en BIOS
2. Configurar interfaz de red:
```bash
sudo ethtool -s eth0 wol g
```
3. Verificar que persiste tras reinicio (añadir a `/etc/network/interfaces` o systemd)

### Comando desde Mac
```bash
# Necesita la MAC del GX10
wakeonlan AA:BB:CC:DD:EE:FF

# Obtener la MAC:
ssh ramon@gx10-ts "ip link show eth0 | grep ether | awk '{print \$2}'"
```

### Alternativa sin WOL
Si WOL no está disponible en BIOS:
- Cron en el GX10: `shutdown -h +1` (apagar en 1 minuto, luego el hardware se enciende solo con "Restore on AC Power Loss" en BIOS)
- O usar un enchufe inteligente controlado por el Mac

---

## 5. Sistema de registro de métricas (obligatorio durante tests)

### Qué registrar SIEMPRE

Cada 10 segundos durante cualquier prueba/auditoría, escribir línea CSV.

**Archivo:** `~/logs/metricas_gx10.csv`

**Columnas:**
| # | Columna | Descripción | Fuente |
|---|---|---|---|
| 1 | `timestamp` | ISO 8601 | `date -Iseconds` |
| 2 | `modelo_cargado` | Qué modelo está en RAM | `ollama ps` o `pgrep llama-server` |
| 3 | `temperatura_gpu` | °C | `nvidia-smi` |
| 4 | `gpu_util` | % utilización | `nvidia-smi` |
| 5 | `vram_usada_gb` | GB usados | `nvidia-smi` |
| 6 | `vram_total_gb` | GB totales | `nvidia-smi` |
| 7 | `power_draw_w` | Vatios actuales | `nvidia-smi` |
| 8 | `ram_sistema_gb` | RAM total usada | `free -g` |
| 9 | `swap_gb` | Swap usado | `free -g` |
| 10 | `cpu_load` | Load average 1 min | `uptime` |
| 11 | `proceso_activo` | Qué script está corriendo | `~/.ura/proceso_activo` |
| 12 | `tamano_paquete` | Items en lote actual | `~/.ura/batch_actual` |
| 13 | `tok_s_prompt` | Velocidad procesamiento | Última respuesta API |
| 14 | `tok_s_gen` | Velocidad generación | Última respuesta API |
| 15 | `items_procesados` | Contador acumulado | `~/.ura/items_done` |
| 16 | `items_pendientes` | Restantes | `~/.ura/items_pending` |
| 17 | `accion_actual` | Estado actual | `~/.ura/accion` |

**Valores de `accion_actual`:**
- `procesando` — trabajando normalmente
- `esperando_modelo` — modelo cargando
- `reduciendo_lote` — batch reducido por temperatura
- `pausa_termica` — detenido por >80°C
- `reinicio_preventivo` — apagando para reinicio al 25/50/75%
- `idle` — sin tarea activa

### Cómo se registra

**Script:** `scripts/registrar_metricas.sh`
Corre en paralelo a cualquier test/auditoría como daemon.

```bash
#!/bin/bash
# registrar_metricas.sh — escribe métricas cada 10s
LOG=~/logs/metricas_gx10.csv

# Header si no existe
if [ ! -f "$LOG" ]; then
    echo "timestamp,modelo,temp,gpu_util,vram_gb,vram_total,power_w,ram_gb,swap_gb,cpu_load,proceso,batch_size,tok_s_prompt,tok_s_gen,items_done,items_pending,accion" > "$LOG"
fi

while true; do
    TS=$(date -Iseconds)
    
    # GPU
    GPU_DATA=$(nvidia-smi --query-gpu=temperature.gpu,utilization.gpu,memory.used,memory.total,power.draw --format=csv,noheader,nounits 2>/dev/null | tr ',' ' ')
    read TEMP GPU_UTIL VRAM_USED VRAM_TOTAL POWER <<< "$GPU_DATA"
    TEMP=${TEMP:-0}; GPU_UTIL=${GPU_UTIL:-0}; VRAM_USED=${VRAM_USED:-0}
    VRAM_TOTAL=${VRAM_TOTAL:-0}; POWER=${POWER:-0}
    
    # RAM
    RAM_GB=$(free -g 2>/dev/null | awk '/^Mem:/ {print $3}')
    SWAP_GB=$(free -g 2>/dev/null | awk '/^Swap:/ {print $3}')
    
    # CPU
    CPU_LOAD=$(uptime | awk -F'load average:' '{print $2}' | awk -F',' '{print $1}' | tr -d ' ')
    
    # Modelo cargado
    MODELO=$(ps -ef 2>/dev/null | grep llama-server | grep -v grep | grep -oP 'gguf' | head -1)
    [ -z "$MODELO" ] && MODELO=$(ollama ps 2>/dev/null | tail -n +2 | awk '{print $1}' | head -1)
    [ -z "$MODELO" ] && MODELO="ninguno"
    [ "$MODELO" = "gguf" ] && MODELO="kimi-dev-72b"
    
    # Estado desde archivos compartidos
    PROCESO=$(cat ~/.ura/proceso_activo 2>/dev/null || echo "idle")
    BATCH=$(cat ~/.ura/batch_actual 2>/dev/null || echo "0")
    TOK_PROMPT=$(cat ~/.ura/tok_s_prompt 2>/dev/null || echo "0")
    TOK_GEN=$(cat ~/.ura/tok_s_gen 2>/dev/null || echo "0")
    DONE=$(cat ~/.ura/items_done 2>/dev/null || echo "0")
    PENDING=$(cat ~/.ura/items_pending 2>/dev/null || echo "0")
    ACCION=$(cat ~/.ura/accion 2>/dev/null || echo "idle")
    
    VRAM_GB=$(echo "scale=1; $VRAM_USED/1024" | bc 2>/dev/null || echo "0")
    VRAM_TOTAL_GB=$(echo "scale=1; $VRAM_TOTAL/1024" | bc 2>/dev/null || echo "0")
    
    echo "$TS,$MODELO,$TEMP,$GPU_UTIL,$VRAM_GB,$VRAM_TOTAL_GB,$POWER,$RAM_GB,$SWAP_GB,$CPU_LOAD,$PROCESO,$BATCH,$TOK_PROMPT,$TOK_GEN,$DONE,$PENDING,$ACCION" >> "$LOG"
    
    sleep 10
done
```

### Archivos de estado (escritos por scripts de tarea)

Cada script de tarea actualiza estos archivos para que el recolector los lea:

| Archivo | Ejemplo | Quién lo escribe |
|---|---|---|
| `~/.ura/proceso_activo` | `kimi_audit` | `kimi_review_limpio.sh` |
| `~/.ura/batch_actual` | `10` | El mismo script de tarea |
| `~/.ura/tok_s_prompt` | `75.8` | Extraído de respuesta API |
| `~/.ura/tok_s_gen` | `2.7` | Extraído de respuesta API |
| `~/.ura/items_done` | `101` | Actualizado cada archivo |
| `~/.ura/items_pending` | `167` | Calculado: total - done |
| `~/.ura/accion` | `procesando` | El script de tarea |

### Análisis posterior

**Script:** `scripts/analizar_metricas.sh`
Lee `metricas_gx10.csv` y genera informe Markdown.

```bash
#!/bin/bash
# analizar_metricas.sh — genera informe de rendimiento
LOG=~/logs/metricas_gx10.csv
OUT=~/docs/informes/rendimiento_$(date +%Y-%m-%d).md

echo "# Informe de rendimiento GX10 — $(date +%Y-%m-%d)" > "$OUT"
echo "" >> "$OUT"

# Temperatura máxima
TEMP_MAX=$(tail -n +2 "$LOG" | awk -F',' '{print $3}' | sort -rn | head -1)
echo "**Temperatura máxima:** ${TEMP_MAX}°C" >> "$OUT"

# VRAM máxima
VRAM_MAX=$(tail -n +2 "$LOG" | awk -F',' '{print $5}' | sort -rn | head -1)
echo "**VRAM máxima:** ${VRAM_MAX} GB" >> "$OUT"

# Velocidad media
AVG_PROMPT=$(tail -n +2 "$LOG" | awk -F',' '$13>0 {sum+=$13; n++} END {printf "%.1f", sum/n}')
AVG_GEN=$(tail -n +2 "$LOG" | awk -F',' '$14>0 {sum+=$14; n++} END {printf "%.1f", sum/n}')
echo "**Velocidad media:** prompt ${AVG_PROMPT} tok/s, gen ${AVG_GEN} tok/s" >> "$OUT"

# Eventos
PAUSAS=$(grep -c "pausa_termica" "$LOG")
REDUCCIONES=$(grep -c "reduciendo_lote" "$LOG")
REINICIOS=$(grep -c "reinicio_preventivo" "$LOG")
echo "**Eventos:** ${PAUSAS} pausas térmicas, ${REDUCCIONES} reducciones, ${REINICIOS} reinicios" >> "$OUT"

# Tiempo activo
LINEAS=$(tail -n +2 "$LOG" | wc -l)
MINUTOS=$((LINEAS / 6))  # 6 muestras por minuto (cada 10s)
echo "**Tiempo muestreado:** ~${MINUTOS} min" >> "$OUT"

echo "**Archivo:** $LOG" >> "$OUT"
```

### Rotación de logs

| Antigüedad | Acción |
|---|---|
| > 30 días | Comprimir con `gzip` |
| > 90 días | Mover a `Toshiba:mac_archive/` |
| < 7 días | Mantener sin comprimir (acceso rápido) |

```bash
# Cron mensual de rotación
0 3 1 * * find ~/logs -name "metricas_gx10*.csv" -mtime +30 -exec gzip {} \;
0 3 1 * * find ~/logs -name "metricas_gx10*.csv.gz" -mtime +90 -exec mv {} /Volumes/TOSHIBA_NUEVO/mac_archive/ \;
```

### Visualización (fase futura)

Dashboard en OpenWebUI/Grafana con:
- Gráfico temperatura en tiempo real
- Gráfico VRAM/RAM
- Velocidad tok/s (prompt y generación)
- Historial: 24h / 7 días / 30 días

---

## 6. Plan de pruebas

| Fase | Qué probar | Cuándo |
|---|---|---|
| 1 | Medir tiempos reales de apagado/arranque | Próxima sesión |
| 2 | Configurar systemd para Ollama + Kimi-Dev | Próxima sesión |
| 3 | Configurar Wake-on-LAN en BIOS GX10 | Próxima sesión |
| 4 | Crear script `mantenimiento_gx10.sh` en Mac | Próxima sesión |
| 5 | Probar reinicio preventivo al 25% | Próxima auditoría grande |
| 6 | Probar reducción térmica (simular calor) | Cuando se pueda forzar |

---

## 7. Estado actual

| Componente | Estado |
|---|---|
| Sistema térmico Nivel 1 (reducción) | Diseñado, no implementado |
| Sistema reinicio Nivel 2 (25/50/75%) | Diseñado, no implementado |
| Wake-on-LAN | No configurado |
| systemd Kimi-Dev | No creado |
| Auditoría en curso | 100/268, GPU 96%, 63°C estable |

---

## 8. No probar ahora

La auditoría Kimi-Dev está en marcha (100/268 archivos). La temperatura es 63°C — muy por debajo de cualquier umbral de riesgo. El sistema está estable. No interrumpir.
