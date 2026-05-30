# Ciclo de mantenimiento del GX10

> **Fecha:** 2026-05-12
> **Estado:** Diseño. NO ejecutar durante auditoría Kimi-Dev.
> **Hardware:** ASUS GX10, 121 GB RAM, NVIDIA GB10

---

## 1. Concepto

Apagar y encender el GX10 periódicamente para:
- Limpiar memoria (evitar memory leaks de procesos largos)
- Cerrar procesos zombi (acumulados tras días de uptime)
- Verificar arranque limpio (detectar servicios rotos)
- Consolidar trabajo (checkpoints guardados antes de apagar)

---

## 2. Métricas a medir (próxima sesión)

### 2.1 Tiempo de apagado limpio
```bash
ssh ramon@gx10-ts "sudo shutdown -h now"
```
Medir hasta que deja de responder al ping:
```bash
ping -c 1 -W 2 gx10-ts && echo "vivo" || echo "apagado"
```

### 2.2 Tiempo de arranque completo
- Wake-on-LAN al GX10
- Medir hasta que SSH responda:
```bash
until ssh -o ConnectTimeout=2 ramon@gx10-ts "echo OK" 2>/dev/null; do sleep 2; done
```

### 2.3 Tiempo de arranque de servicios
- Hasta que Ollama responda: `curl http://gx10-ts:11434/api/tags`
- Hasta que Kimi-Dev responda: `curl http://gx10-ts:8088/health`

### 2.4 Tiempo de recarga del modelo
- Cargar Kimi-Dev otra vez (5-6 minutos estimados)
- Medir desde `llama-server` launch hasta primer `{"status":"ok"}`

### 2.5 Tiempo total del ciclo
```
apagar + esperar + arrancar + servicios + cargar modelo + reanudar checkpoint
```

---

## 3. Frecuencia propuesta (revisar tras medir)

| Caso | Frecuencia |
|---|---|
| Durante auditoría larga | **NO apagar** (interrumpe trabajo) |
| Mantenimiento rutinario | Cada 7 días |
| Tras crash o cuelgue | Inmediatamente |
| Tras update del SO | Inmediatamente |
| Tras instalar paquetes nuevos | Inmediatamente |

---

## 4. Requisitos previos

### 4.1 Servicios que autoarrancan al encender

| Servicio | Gestor | Estado |
|---|---|---|
| Ollama | systemd | Verificar `systemctl enable ollama` |
| llama-server (Kimi-Dev) | systemd unit nuevo | Pendiente crear |
| SSH | systemd | Ya activo |
| Tailscale | systemd | Ya activo |

systemd unit para Kimi-Dev (a crear):
```ini
# /etc/systemd/system/kimi-dev.service
[Unit]
Description=Kimi-Dev-72B llama-server
After=network.target

[Service]
User=ramon
ExecStart=/home/ramon/llama.cpp/build_cuda/bin/llama-server \
  -m /home/ramon/models/kimi-dev/Kimi-Dev-72B-abliterated-Q8_0.gguf \
  --host 0.0.0.0 --port 8088 \
  --threads 4 --threads-batch 2 \
  -ngl 80 --ctx-size 4096
Restart=no

[Install]
WantedBy=default.target
```

### 4.2 Checkpoint reanudable

| Script | Checkpoint | Estado |
|---|---|---|
| `kimi_review_limpio.sh` | `~/logs/kimi_review/checkpoint.txt` | ✅ |
| Otros scripts | A verificar | ❓ |

### 4.3 Detección automática de tarea pendiente

Al arrancar, comprobar si hay una auditoría a medias:
```bash
if [ "$(wc -l < ~/logs/kimi_review/checkpoint.txt)" -lt 268 ]; then
    echo "Auditoría pendiente — reanudando..."
    ~/bin/kimi_review_limpio.sh core
fi
```

### 4.4 Control remoto desde Mac

| Acción | Comando |
|---|---|
| Apagar | `ssh ramon@gx10-ts "sudo shutdown -h now"` |
| Encender | Wake-on-LAN (configurar en BIOS GX10) |
| Verificar vivo | `ping gx10-ts` |
| Reanudar auditoría | `ssh ramon@gx10-ts "screen -dmS kimi ~/bin/kimi_review_limpio.sh core"` |

---

## 5. Script propuesto — `mantenimiento_gx10.sh` (en Mac)

```bash
#!/bin/bash
# mantenimiento_gx10.sh — apagado/encendido seguro del GX10
# Ejecutar desde el Mac vía cron (ej. domingos 03:00)

GX10="gx10-ts"
CHECKPOINT="/home/ramon/logs/kimi_review/checkpoint.txt"
TOTAL_CORE=268

echo "[$(date)] Iniciando mantenimiento GX10..."

# 1. Verificar si hay tarea crítica corriendo
PENDIENTES=$(ssh ramon@$GX10 "wc -l < $CHECKPOINT 2>/dev/null" 2>/dev/null || echo "0")
if [ "$PENDIENTES" -gt 0 ] && [ "$PENDIENTES" -lt "$TOTAL_CORE" ]; then
    echo "Auditoría Kimi en progreso ($PENDIENTES/$TOTAL_CORE). Saltando mantenimiento."
    exit 0
fi

# 2. Apagar limpio
echo "Apagando GX10..."
ssh ramon@$GX10 "sudo shutdown -h now" 2>/dev/null

# 3. Esperar apagado
sleep 30
while ping -c 1 -W 2 $GX10 >/dev/null 2>&1; do
    echo "Esperando apagado..."
    sleep 5
done
echo "GX10 apagado"

# 4. Esperar 60s
sleep 60

# 5. Wake-on-LAN (requiere MAC address del GX10)
# wakeonlan XX:XX:XX:XX:XX:XX

# 6. Esperar SSH disponible
echo "Esperando arranque..."
until ssh -o ConnectTimeout=5 ramon@$GX10 "echo OK" 2>/dev/null; do
    sleep 5
done
echo "GX10 arrancado, SSH disponible"

# 7. Verificar servicios
sleep 10
ssh ramon@$GX10 "curl -s --max-time 5 http://localhost:11434/api/tags >/dev/null 2>&1 && echo 'Ollama OK' || echo 'Ollama PENDIENTE'"

# 8. Notificar
echo "[$(date)] Mantenimiento GX10 completado"
```

---

## 6. Plan próxima sesión

1. **Medir tiempos reales** de apagado, arranque, carga de modelo
2. **Configurar systemd** para Ollama + Kimi-Dev autoarranque
3. **Configurar Wake-on-LAN** en BIOS del GX10
4. **Crear script** `mantenimiento_gx10.sh` en Mac
5. **Cron semanal** en Mac (domingos 03:00 AM)

---

## 7. Estado actual

| Componente | Estado |
|---|---|
| Tiempos medidos | ❌ Pendiente |
| systemd Ollama | ⚠️ Verificar |
| systemd Kimi-Dev | ❌ No creado |
| Wake-on-LAN | ❌ No configurado |
| Script mantenimiento | ❌ No creado |
| Cron semanal | ❌ No configurado |
| Auditoría en curso | ✅ 89/268 procesados |

---

## 8. NO HACER AHORA

La auditoría Kimi-Dev está en marcha (89/268 archivos, ETA ~18:30).
**Apagar ahora = perder 5 horas de trabajo.**
Esperar a que termine la auditoría antes de probar el ciclo de apagado.
