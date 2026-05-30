# Informe de Ejecuciones de Auditoría — 2026-05-12/13

## 1. Kimi-Dev 72B — 12 mayo
**Cómo se ejecutó:** `kimi_code_review.py` desde Mac → llama.cpp CUDA en GX10:8088
**Archivos:** 268 (core/ completo)
**Resultado:** 196/268 completados (73%), 404 KB de informe
**Problema:** 95% ruido narrativo, solo 15 bugs reales (5% acierto)
**Informe:** `review_20260512_1125.md` ✅ Guardado (399 KB)

---

## 2. Codestral 22B — 12 mayo (interactivo)
**Cómo se ejecutó:** Conversación en vivo, enviando archivos uno a uno al GX10
**Archivos:** 33 CRITICAL
**Resultado:** 102 bugs con línea exacta + fix, 12.6 minutos
**Problema:** **NO SE GUARDÓ A DISCO.** Solo quedó en la conversación.
**Informe:** ❌ Perdido

---

## 3. Qwen2.5-Coder Q8 — 12 mayo (interactivo)
**Cómo se ejecutó:** Conversación en vivo, prueba de comparativa
**Archivos:** 3-4 de prueba
**Resultado:** Buen rendimiento, 87s/archivo
**Problema:** **NO SE GUARDÓ A DISCO.** Solo prueba, no auditoría completa.
**Informe:** ❌ Perdido

---

## 4. Auditoría Multi-modelo Ollama v1 — 13 mayo mañana
**Cómo se ejecutó:** `auditoria_multimodelo.sh` en GX10, usando Ollama API
**Archivos:** 28 CRITICAL × 4 modelos
**Resultado:** **TODO "NO EXISTE"** — los archivos no estaban en el GX10
**Problema:** El proyecto URA solo existe en el Mac. Nadie copió los archivos.
**Informe:** `review_codestral_22b_20260513_1002.md` ❌ Vacío

---

## 5. Auditoría Multi-modelo Ollama v2 — 13 mayo
**Cómo se ejecutó:** rsync del Mac al GX10, re-ejecución de auditoria_multimodelo.sh
**Archivos:** 28 CRITICAL × 4 modelos
**Resultado:** Arrancó pero se cortó al reiniciar Ollama para configurar MAX_LOADED_MODELS
**Problema:** Misma causa que #4 — el ciclo "configurar → reiniciar → matar auditoría"
**Informe:** `review_*_20260513_1015.md` ❌ Parcial

---

## 6. llama.cpp Router + Auditoría v3 — 13 mayo
**Cómo se ejecutó:**
- Se borraron 5 modelos rotos de Ollama (99 GB liberados)
- Se configuró `OLLAMA_MAX_LOADED_MODELS=4` en systemd
- Se copiaron GGUFs de Ollama a ~/models/llama-cpp/
- Se creó `llama_router.py` (puerto 8288, 3 modelos simultáneos)
- Se ejecutó `auditoria_llamacpp.sh` usando API OpenAI-compatible

**Archivos:** 28 CRITICAL × 3 modelos (codestral-22b, qwen2.5-coder-q8, qwen2.5-coder-32b)

**Problema:** `head -500` en el script **truncó el código** antes de enviarlo. Los modelos solo vieron las primeras 500 líneas de cada archivo. Además, sin contexto del proyecto (CONTEXTO_REVISION.md), los modelos alucinan o no encuentran nada.

**Resultado:**
| Modelo | Bugs reales | Falsos positivos | Tamaño informe |
|--------|------------|-----------------|----------------|
| Codestral 22B | 3 | 10+ | 25 KB |
| Qwen2.5-Coder Q8 | 2 | 0 | 4.2 KB |
| Qwen2.5-Coder 32B | 2 | 6 | 4.2 KB |

**Informe:** `review_codestral-22b_20260513_1033.md` ⚠️ Sesgado por truncamiento

---

## 7. OpenCode Manual Review — 13 mayo
**Cómo se ejecutó:** Lectura directa de los archivos Python por OpenCode (sin LLM externo)
**Archivos:** 27 archivos (core/ + agents/ + security/)
**Resultado:** **50 bugs reales** — 15 CRASH, 25 lógica, 10 estilo
**Informe:** `REVIEW_OPENCODE_20260513.md` ✅ Guardado (12 KB)

---

## PROBLEMAS DETECTADOS EN TODO EL PROCESO

### Problema 1: Los archivos no están en el GX10
- El proyecto URA vive en el Mac
- Las auditorías corren en el GX10 (el que tiene GPU)
- Si no se copian antes, los scripts fallan
- **Solución:** rsync antes de cada auditoría o usar API desde el Mac enviando el código

### Problema 2: Truncamiento con `head -500`
- El script limitaba cada archivo a 500 líneas
- Los bugs más profundos nunca se vieron
- **Solución:** Enviar archivo completo (o al menos 1500 líneas)

### Problema 3: Sin contexto del proyecto
- Los modelos no saben qué hace cada archivo
- Sin CONTEXTO_REVISION.md, alucinan imports y relaciones
- **Solución:** Incluir CONTEXTO_REVISION.md en el prompt del sistema

### Problema 4: Prompt genérico → respuestas vagas
- "Revisa este código" produce narrativa, no bugs
- **Solución:** Prompt directivo: "SOLO bugs con línea exacta. Formato: LÍNEA | QUÉ FALLA | CÓMO ARREGLARLO"

### Problema 5: Informes no guardados
- Las revisiones interactivas (Codestral 102 bugs) no se guardaron
- **Solución:** Siempre dirigir salida a archivo

### Problema 6: Ciclo "configurar → reiniciar → matar"
- Configurar Ollama requiere reinicio
- Reiniciar mata la auditoría en curso
- **Solución:** Configurar ANTES de lanzar, nunca durante

---

## LECCIONES

1. **Sin contexto = sin bugs.** El prompt debe incluir qué hace el archivo.
2. **Código completo o nada.** `head -500` es inútil.
3. **Guardar siempre.** Si no está en disco, no existe.
4. **Los LLMs solos no bastan.** OpenCode leyendo el código encontró 50 bugs, los modelos encontraron 2-3.
5. **El prompt manda.** "SOLO bugs" funciona. "Revisa este código" no.

---

## PRÓXIMA EJECUCIÓN (CORREGIDA)

```bash
# 1. Sincronizar archivos
rsync -avz ~/URA/ura_ia_1972/core/ gx10:~/URA/ura_ia_1972/core/

# 2. Enviar archivo COMPLETO (sin head)
CODE=$(cat "$FP")

# 3. Incluir contexto en el prompt del sistema
SYSTEM_PROMPT="Eres un revisor de codigo Python en el proyecto URA.
Contexto: $(cat CONTEXTO_REVISION.md)
SOLO reporta bugs reales con: LINEA | QUE FALLA | COMO ARREGLARLO.
NO des sugerencias. Si no hay bugs, di OK."

# 4. Guardar siempre
OUT="~/logs/auditoria_multimodelo/review_${MODEL}_$(date +%Y%m%d_%H%M).md"
```
