# Proceso de Auditoría Kimi-Dev

> **Fecha:** 2026-05-12
> **Modelo:** Kimi-Dev-72B-abliterated Q8_0 (72 GB)
> **Servidor:** GX10, llama.cpp CUDA

---

## 1. Configuración óptima

| Parámetro | Antes | Ahora | Motivo |
|---|---|---|---|
| `--ctx-size` | 4096 | **8192** | Batch de 2 archivos con ~4000 chars c/u |
| `--threads` | 4 | 4 | Sin cambios |
| `-ngl` | 80 | 80 | Todas las capas en GPU |
| `--threads-batch` | 2 | 2 | Sin cambios |
| Batch size | 1 archivo | **2 archivos** | Ahorro 38% de tiempo |
| Auto-throttle | — | v2 (subida lenta +10%/10min) | Busca límite real del HW |

---

## 2. Velocidad y tiempos

| Modo | Tiempo/archivo | 268 archivos |
|---|---|---|
| Batch=1 (ctx 4096) | 168s | **12.5 horas** |
| Batch=2 (ctx 4096) | No viable (solo <1000 chars) | — |
| **Batch=2 (ctx 8192)** | 105s | **7.8 horas** |
| Ahorro vs batch=1 | **38%** | **-4.7 horas** |

---

## 3. Flujo de auditoría

### 3.1 Script recomendado: `kimi_review_robusto.sh` ✅

**Auto-protección anti-bloqueo:**
- Timeout de 10 minutos por archivo
- Si un archivo se bloquea → lo salta automáticamente
- Registra el archivo problemático en `bloqueados.log`
- Continúa con el siguiente sin intervención manual
- Al final, muestra lista de archivos que necesitan revisión manual

```bash
# Lanzar (siempre usar este, no el antiguo)
ssh ramon@gx10-ts "nohup ~/bin/kimi_review_robusto.sh > ~/logs/kimi_review/run.log 2>&1 &"
```

### 3.2 Inicio completo
```bash
# 1. Asegurar Kimi-Dev corriendo con ctx 8192
curl http://gx10-ts:8088/health

# 2. Resetear checkpoint
ssh ramon@gx10-ts "> ~/logs/kimi_review/checkpoint_batch.txt"

# 3. Lanzar auto-throttle
ssh ramon@gx10-ts "nohup ~/bin/auto_throttle_paquetes.sh > /dev/null 2>&1 &"

# 4. Lanzar auditoría batch
ssh ramon@gx10-ts "nohup ~/bin/kimi_review_batch.sh core > ~/logs/kimi_review/run_batch.log 2>&1 &"
```

### 3.2 Durante la auditoría
```bash
# Progreso
ssh ramon@gx10-ts "wc -l ~/logs/kimi_review/checkpoint_batch.txt"

# Auto-throttle
ssh ramon@gx10-ts "tail -5 ~/logs/auto_throttle.log"

# Temperatura
ssh ramon@gx10-ts "nvidia-smi --query-gpu=temperature.gpu --format=csv,noheader"
```

### 3.3 Post-auditoría
```bash
# Automático: post_auditoria_kimi.sh
# - Guarda informe al Mac
# - Reinicia Kimi-Dev con ctx 8192 para próxima
# - Verifica batch funciona

# Manual:
ssh ramon@gx10-ts "~/bin/post_auditoria_kimi.sh"
```

---

## 4. Auto-throttle v2

- **Subida:** +10% cada 10 minutos si T<80°C y VRAM<90%
- **Bajada:** -10% inmediato si T≥86°C o VRAM≥96%
- **Guardia:** máximo 200 (sanidad)
- **Mínimo:** 2

Valor actual recomendado se lee de: `~/.config/limites/paquete_kimi.lote_maximo`

---

## 5. Límites del sistema

| Métrica | Límite | Acción |
|---|---|---|
| Temperatura | 86°C | auto-throttle baja batch |
| VRAM | 96% | auto-throttle baja batch |
| Contexto | 8192 tokens | Si se excede → error 500 |
| Archivo >50 KB | No se revisa | `-size -50k` en find |
| Código >4000 chars | Batch=1 automático | Fallback del script |

---

## 6. Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| "Context size exceeded" | Prompt demasiado largo | Reducir chars por archivo o usar batch=1 |
| Batch parsing falla | Modelo no respetó delimitadores | Script hace fallback a individual |
| Servidor no arranca | ctx 8192 consume más VRAM | Bajar a 4096, revisar VRAM libre |
| Temperatura >86°C | Carga excesiva | Auto-throttle baja batch automáticamente |

---

## 7. Scripts

| Script | Función | Cuándo usar |
|---|---|---|
| **`kimi_review_robusto.sh`** ✅ | **Auto-skip archivos bloqueados (timeout 10min)** | **SIEMPRE** |
| `kimi_review_limpio.sh` | Batch=1, secuencial | Legacy |
| `kimi_review_batch.sh` | Batch=2, ahorra 38% | Con ctx=8192 |
| `kimi_batch_helper.py` | Helper Python para batch de 2 | Interno |
| `auto_throttle_*.sh` | Ajusta batch según temp/VRAM | En paralelo |
| `post_auditoria_kimi.sh` | Migra servidor a ctx 8192 | Tras auditoría |

## 8. Bloqueos y recuperación

**Si un archivo bloquea la revisión:**
1. El script robusto lo salta automáticamente (timeout 10 min)
2. Lo registra en `~/logs/kimi_review/bloqueados.log`
3. El checkpoint avanza al siguiente
4. Revisar `bloqueados.log` después para depurar manualmente

**Reanudar tras parada:**
```bash
ssh ramon@gx10-ts "nohup ~/bin/kimi_review_robusto.sh > ~/logs/kimi_review/run.log 2>&1 &"
```
El checkpoint se conserva — continúa donde se quedó.
