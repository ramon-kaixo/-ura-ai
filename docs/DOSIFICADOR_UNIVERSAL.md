# Dosificador Universal de Tareas — Patrón de Control Adaptativo

> **Fecha:** 2026-05-12
> **Servidor:** GX10 (ASUS, 121 GB RAM, NVIDIA GB10)
> **Principio:** Una sola lógica para todas las tareas pesadas

---

## 1. Concepto

El cuello de botella en URA no es el tipo de dato (PDF, vídeo, imagen, código). Es el **consumo de recursos** (GPU, RAM, CPU) en el GX10. Cuando la tasa de entrada (peticiones) supera la tasa de salida (procesamiento), el sistema se atasca. La solución es un **dosificador** que regule el caudal según métricas en tiempo real.

```
Tasa de entrada ──→ [DOSIFICADOR] ──→ Tasa de salida
(peticiones)         (factor 0.15-1.0)  (procesamiento)
                         │
                    ┌────┴────┐
                    │ Métricas │
                    │ GPU, CPU,│
                    │ RAM      │
                    └─────────┘
```

---

## 2. Arquitectura

### Componente 1 — Daemon controlador de recursos

**Archivo:** `~/bin/controlador_recursos.sh`
**Intervalo:** 10 segundos

Mide GPU, load average, RAM libre. Calcula `FACTOR` (0.15 a 1.0) según saturación. Escribe límites dinámicos:

```
~/.config/limites/
├── kimi.lote_maximo
├── documentos.lote_maximo
├── video.lote_maximo
├── imagenes.lote_maximo
├── audio.lote_maximo
├── embeddings.lote_maximo
├── ocr.lote_maximo
├── PAUSA_GLOBAL
└── estado.txt
```

**Umbrales:**
| Métrica | Límite | Acción |
|---|---|---|
| GPU > 75% | Reduce factor ×0.7 |
| Load avg > 5.5 | Reduce factor ×0.7 |
| RAM > 85% | Reduce factor ×0.5 |
| Factor < 0.25 | Activa PAUSA_GLOBAL |

### Componente 2 — Pausa global

**Archivo:** `~/.config/limites/PAUSA_GLOBAL`

Si existe, todas las tareas se detienen inmediatamente (esperan 30s y reintentan). Útil para mantenimiento, emergencias, o cuando el sistema está al borde del colapso.

```bash
# Activar
touch ~/.config/limites/PAUSA_GLOBAL

# Desactivar
rm ~/.config/limites/PAUSA_GLOBAL
```

### Componente 3 — Scripts adaptativos por tarea

**Patrón estándar:**
```bash
#!/bin/bash
while true; do
    # Respetar pausa global
    [ -f ~/.config/limites/PAUSA_GLOBAL ] && sleep 30 && continue

    # Leer límite dinámico
    LIMITE=$(cat ~/.config/limites/mi_tarea.lote_maximo 2>/dev/null || echo "5")

    # Procesar hasta LIMITE archivos
    for f in $(ls ~/pendientes/mi_tarea/*.ext | head -n $LIMITE); do
        procesar "$f"
        echo "$f" >> ~/.checkpoint/mi_tarea.log  # Checkpoint
    done

    sleep 10
done
```

### Componente 4 — Checkpoint de progreso

Cada tarea registra qué archivos ha procesado. Si se reinicia, recupera el punto donde se quedó.

```
~/.checkpoint/
├── kimi_review.log
├── documentos.log
├── video.log
└── ...
```

---

## 3. Tareas planificadas

| Tarea | Modelo | Lote base | Input | Tipo |
|---|---|---|---|---|
| `revision_codigo` | qwen2.5-coder:32b | 10 | Archivos .py | Código |
| `documentos` | qwen3:32b | 15 | PDFs vía pdftotext | Texto |
| `video` | whisper large | 3 | ffmpeg→wav→transcripción | Audio |
| `imagenes` | llava:13b | 5 | Archivos .jpg/.png | Visual |
| `audio` | whisper large | 5 | Archivos .mp3/.wav | Audio |
| `embeddings` | mxbai-embed-large | 50 | Documentos indexados | Vectores |
| `ocr` | qwen2.5-vl:7b | 8 | Fotos/scans con texto | Visual |

**Nota:** Kimi-Dev-72B Q8_0 (72 GB) no carga en la GB10. Alternativas en investigación (ver sección 6). Para revisión de código diaria → qwen2.5-coder:32b vía Ollama.

---

## 4. Rotación cada 6h (sandboxes)

Los sandboxes del ciclo evolutivo usan el mismo patrón adaptativo:

| Hora | Sandbox 1 | Sandbox 2 | Propósito |
|---|---|---|---|
| 06:00 | Mantenimiento | Seguridad | Limpieza + Validación |
| 12:00 | Aprendizaje | Documentación | Procesamiento + Informes |
| 18:00 | Mantenimiento | Aprendizaje | Limpieza + Procesamiento |
| 00:00 | Seguridad | Documentación | Validación + Informes |

---

## 5. Integración con URA

```
central_router.process_request()
    │
    ├── detecta tipo de tarea
    ├── encola en ~/pendientes/<tipo>/
    ├── forensic_scribe registra: "encolado: <tipo> <archivo>"
    │
    └── script adaptativo (daemon en screen/nohup)
        │
        ├── lee ~/.config/limites/<tipo>.lote_maximo
        ├── procesa al ritmo permitido
        ├── checkpoint en ~/.checkpoint/<tipo>.log
        └── forensic_scribe registra: "procesado: <tipo> <archivo> <resultado>"
            │
            └── agente_verificador_tareas
                │
                ├── detecta colas atascadas (>30 min sin procesar)
                └── alerta vía Pushover
```

---

## 6. Estado actual

| Componente | Estado |
|---|---|
| `controlador_recursos.sh` | Implementado y corriendo (nohup) |
| `kimi_review_adaptativo.sh` | Implementado (Kimi-Dev no carga en GB10) |
| `documentos_adaptativo.sh` | Diseñado, pendiente activar |
| `video_adaptativo.sh` | Diseñado, pendiente activar |
| `lanzar_todos_modelos.sh` | Implementado (screen) |
| Otros tipos (imagen, audio, ocr) | Pendientes |
| Integración central_router | Pendiente |
| Conexión forensic_scribe | Pendiente |
| Conexión agente_verificador | Pendiente |

### Investigación Kimi-Dev en GB10

**Resultado:** Kimi-Dev-72B Q8_0 (72 GB) no carga en NVIDIA GB10 con llama.cpp CUDA. El proceso muere durante la carga de tensores (`load_tensors`) sin error visible. Probado con `-ngl 80`, `-ngl 40`, y `-ngl 0`.

**Alternativas encontradas:**
| Repo | Quant | Tamaño estimado |
|---|---|---|
| `unsloth/Kimi-Dev-72B-GGUF` | IQ4_NL | ~25 GB |
| `bartowski/moonshotai_Kimi-Dev-72B-GGUF` | IQ4_XS | ~22 GB |
| `gabriellarson/Kimi-Dev-72B-GGUF` | Q4_K_M | ~30 GB |

**Próximo paso:** Descargar `unsloth/Kimi-Dev-72B-GGUF IQ4_NL` (~25 GB) y probar en el GX10. Si carga, usar para revisión. Si no, usar qwen2.5-coder:32b como plan B definitivo.

**Ollama:** Kimi-Dev no está disponible en Ollama (404 en ollama.com/library/kimi).

**vLLM:** No instalado en GX10. Requiere PyTorch con CUDA.

---

## 7. Ventajas del patrón

- **Una sola lógica** para todas las tareas (mantenimiento simple)
- **Auto-ajuste** según carga real del sistema
- **Resiliencia** ante reinicios (checkpoints)
- **Pausa global** de emergencia
- **Tareas no se pisan** entre ellas (cada una lee su propio límite)
- **Escalable**: añadir nuevos tipos solo requiere un script más

---

## 8. Comandos rápidos

```bash
# Ver estado del controlador
cat ~/.config/limites/estado.txt

# Activar pausa global
touch ~/.config/limites/PAUSA_GLOBAL

# Desactivar pausa global
rm ~/.config/limites/PAUSA_GLOBAL

# Ver screens activas
screen -ls

# Ver progreso de checkpoint
wc -l ~/.checkpoint/kimi_review.log

# Lanzar todos los servicios
~/bin/lanzar_todos_modelos.sh
```
