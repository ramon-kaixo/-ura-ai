# Sistema URA — Revisión de código autónoma con Kimi-Dev-72B

> Última actualización: 2026-05-12
> Modelo: Kimi-Dev-72B-abliterated Q8_0 (72 GB)
> Servidor: GX10 (ASUS, 121 GB RAM, GPU NVIDIA GB10, CUDA 13.0)
> Orquestador: Mac (interfaz, PM2, nginx, dashboard)

---

## 1. Propósito del sistema

Revisión automática nocturna de los ~589 archivos Python del proyecto URA (42 MB).
Un humano no puede revisar manualmente todo el código cada día.

---

## 2. Por qué Kimi-Dev y no otro modelo

| Modelo | Ventaja | Desventaja |
|---|---|---|
| **Kimi-Dev-72B** | 60.4% SWE-bench, razonamiento dual (BugFixer+TestWriter) | Requiere llama.cpp con MLA, sin soporte Ollama |
| Qwen2.5-Coder 32B | Simple (Ollama), rápido | Análisis superficial |
| DeepSeek-R1 70B | Razonamiento | Más lento, no cabe en GPU |
| Codestral 22B | Ligero | Poco profundo para auditoría |

**Decisión:** Kimi-Dev para auditoría profunda nocturna. Qwen2.5-Coder para uso diario interactivo.

---

## 3. Límites de recursos — por qué existen

El GX10 ejecuta otros servicios de día (Ollama, Docker, Langfuse). Sin límites:
- Sistema inaccesible por SSH (ocurrió en primera prueba)
- Riesgo de corrupción de BD/logs por cuelgue

| Límite | Valor | Propósito |
|---|---|---|
| `nice -n 19` | Prioridad mínima | Otras tareas primero |
| `cpulimit 60%` | Nunca >60% CPU | Margen para SO y SSH |
| `--threads 4` | 4 de 20 núcleos | Resto para sistema |
| `-ngl 80` | 80 capas GPU | Margen para SO |
| `timeout 8h` | Auto-kill | No bloquear el sistema indefinidamente |
| Watchdog SSH | Cada 30s | Si SSH muere → kill |
| Cron load > 6 | Cada 2 min | Si carga >6 → kill |

---

## 4. Checkpoint — por qué

Primera revisión: ~24-30h. Si se interrumpe, no empezar de cero.
`checkpoint.txt` guarda archivos ya procesados. Al reanudar, los omite.

---

## 5. Históricos y aprendizaje — por qué

- Comparar informes mensuales → ver evolución del código
- Acumular fallos reales → futuro fine-tune/LoRA
- Auditoría humana → solo leer fallos críticos

---

## 6. Restauración post-revisión — por qué

Modo nocturno (Kimi-Dev, pesado) vs modo diurno (Ollama, interactivo).
Al terminar: kill Kimi-Dev → arrancar Ollama. Separación estricta.

---

## 7. Roadmap

| Plazo | Objetivo |
|---|---|
| **Corto** | Revisión completa con informes Markdown estructurados |
| **Medio** | Histórico de fallos → Kimi recomienda cambios concretos |
| **Largo** | LoRA fine-tune con datos propios de URA |

---

## 8. Instrucciones para Kimi-Dev (system prompt)

```
Eres un revisor de código Python especializado en el proyecto URA.
Trabajas de noche en un servidor con recursos limitados (GX10, 121 GB RAM, GPU GB10).

Reglas:
1. Sé CONCISO. No divagues. El log se procesa automáticamente.
2. Prioriza: CRITICAL > HIGH > MEDIUM > LOW.
3. Si el mismo patrón aparece en varios archivos, menciónalo: "PATRÓN RECURRENTE: ..."
4. Usa formato Markdown: títulos ##, listas -, código entre ```
5. Clasifica cada hallazgo: [BUG] [SEGURIDAD] [RENDIMIENTO] [ESTILO] [MEJORA]
6. Si no hay problemas en un archivo, responde solo: "OK"
7. No sugieras instalar librerías externas sin justificar.
8. Prioriza correcciones que no rompan compatibilidad.

Ejemplo de respuesta esperada:
## agent_bridge.py
- [ESTILO] L12: línea demasiado larga (>120 chars)
- [BUG] L45: posible división por cero en calcular_ratio()
OK el resto del archivo.
```

---

## 9. Archivos del sistema

| Archivo | Ubicación | Propósito |
|---|---|---|
| `kimi_review_seguro.sh` | `~/` en GX10 | Script principal con límites + watchdog + checkpoint |
| `checkpoint.txt` | `~/logs/kimi_review/` | Archivos ya revisados |
| `review_YYYYMMDD_HHMM.md` | `~/logs/kimi_review/` | Resultado de cada revisión |
| `run.log` | `~/logs/kimi_review/` | Log de ejecución del script |
| `watchdog.log` | `~/logs/kimi_review/` | Alertas del watchdog |
| `Kimi-Dev-72B-abliterated-Q8_0.gguf` | `~/models/kimi-dev/` | Modelo GGUF (72 GB) |
| `llama.cpp/build_cuda/` | `~/llama.cpp/` | Servidor compilado con CUDA |

---

## 10. Comandos rápidos

```bash
# Lanzar revisión
ssh ramon@gx10-ts "nohup ~/kimi_review_seguro.sh > ~/logs/kimi_review/run.log 2>&1 &"

# Ver progreso (archivos revisados)
ssh ramon@gx10-ts "wc -l ~/logs/kimi_review/checkpoint.txt"

# Ver últimos resultados
ssh ramon@gx10-ts "tail -50 ~/logs/kimi_review/review_*.md"

# Parar (guarda progreso)
ssh ramon@gx10-ts "pkill -f kimi_review_seguro"

# Reanudar
ssh ramon@gx10-ts "nohup ~/kimi_review_seguro.sh > ~/logs/kimi_review/run.log 2>&1 &"

# Estado del servidor
ssh ramon@gx10-ts "nvidia-smi --query-gpu=utilization.gpu,memory.used,temperature.gpu --format=csv,noheader"
```
