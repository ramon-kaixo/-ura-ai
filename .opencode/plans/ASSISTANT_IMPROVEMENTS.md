# Plan de Mejoras Rápidas — Asistente Conversacional

## Orden de Ejecución

Las mejoras están ordenadas para minimizar riesgo: primero las que solo conectan datos ya existentes (sin riesgo de rotura), luego las que añaden funcionalidad nueva.

---

## Paso 1 — Conectar datos huérfanos al prompt (30 min total)

**Riesgo:** Muy bajo. Solo se añaden 3 líneas al `_build_system_prompt()`.

### 1a. Proactive Suggestion (15 min)
- **Archivo:** `motor/assistant/api.py`
- **Función:** `_build_system_prompt()`
- **Cambio:** Añadir:
```python
if analysis.get("proactive_suggestion"):
    system_prompt += f"\n[Nota: {analysis['proactive_suggestion']}]"
```
- **Verificación:** Enviar "recuérdame revisar el backup" → luego "hola" → debe sugerir la tarea

### 1b. Response Adjustments (15 min)
- **Archivo:** `motor/assistant/api.py`
- **Función:** `_build_system_prompt()`
- **Cambio:** Añadir:
```python
adj = analysis.get("response_adjustments", {})
if adj.get("apologize"):
    system_prompt += " El usuario puede estar frustrado. Discúlpate."
if adj.get("shorten"):
    system_prompt += " Responde muy breve."
if adj.get("clarify"):
    system_prompt += " Pregunta si necesita aclaración."
```
- **Verificación:** Enviar mensaje con "no me convence" → debe disculparse

---

## Paso 2 — Expandir patrones de intención (30 min)

**Riesgo:** Bajo. Solo se añaden palabras a regex existentes.

### Archivo: `motor/assistant/intent.py`
- **Línea 73:** Añadir al patrón COMMAND:
```
comprueba|verifica|chequea|analiza|examina|compara|avísame|notifícame|traduce|sintetiza|ordena|organiza|convierte|transforma|instala|configura|borra
```
- **Línea 65:** Añadir al patrón QUESTION:
```
cómo se hace|dónde está|cuál es
```

### Verificación:
- "comprueba el estado" → intent=COMMAND
- "analiza este código" → intent=COMMAND
- "cómo se hace un commit" → intent=QUESTION

---

## Paso 3 — DateTime Tool (30 min)

**Riesgo:** Bajo. Tool nueva, no afecta a nada existente.

### Archivo: `motor/assistant/executor.py`
- Añadir clase `DateTimeTool`:
```python
class DateTimeTool:
    def execute(self) -> ToolResult:
        from datetime import datetime
        now = datetime.now()
        return ToolResult(True, (
            f"Fecha: {now.strftime('%d/%m/%Y')}\n"
            f"Hora: {now.strftime('%H:%M:%S')}\n"
            f"Día de la semana: {now.strftime('%A')}\n"
            f"Hora local: {now.strftime('%H:%M')}"
        ))
```

### Archivo: `motor/assistant/executor.py` — `ConversationalToolManager.execute()`
- Añadir ruta:
```python
if tool_name == "datetime":
    return self._datetime.execute()
```
- Añadir al `__init__`: `self._datetime = DateTimeTool()`

### Archivo: `motor/assistant/api.py` — `_execute_command()`
- Añadir keyword mapping: `"hora" → "datetime"`, `"fecha" → "datetime"`, `"día" → "datetime"`

### Verificación:
- "qué hora es" → devuelve fecha y hora actual

---

## Paso 4 — Endpoint de feedback explícito (1h)

**Riesgo:** Medio. Nuevo endpoint, no afecta a los existentes.

### Archivo: `motor/assistant/api.py`
- Añadir nuevo modelo:
```python
class FeedbackRequest(BaseModel):
    conversation_id: str
    rating: int = Field(..., ge=1, le=5)
    comment: str = ""
```
- Añadir nuevo endpoint:
```python
@router.post("/feedback")
async def feedback(req: FeedbackRequest) -> dict:
    # Validar que la conversación existe
    conv = get_engine().get_conversation(req.conversation_id)
    if not conv:
        raise HTTPException(404, "Conversación no encontrada")
    # Registrar en evaluator
    from motor.assistant.evaluation import ConversationEvaluator
    ev = ConversationEvaluator()
    ev.record_metric(req.conversation_id, "user_rating", float(req.rating), {"comment": req.comment})
    return {"status": "ok", "rating": req.rating}
```

### Verificación:
- `POST /api/v1/chat/feedback {"conversation_id":"...","rating":4}` → 200

---

## Paso 5 — Herramientas básicas (5-7 herramientas, 1.5h)

**Riesgo:** Medio. Nuevas tools, probar cada una individualmente.

### Archivo: `motor/assistant/executor.py`

Añadir estas herramientas:

1. **FileReadTool** — Lee archivos del sistema (con whitelist de directorios)
2. **FileListTool** — Lista archivos en un directorio
3. **SystemInfoTool** — RAM, CPU, disco
4. **CalculatorTool** — Evalúa expresiones matemáticas
5. **NoteTool** — Toma/recupera notas rápidas (SQLite)
6. **UrlFetchTool** — Obtiene contenido de una URL
7. **DateTimeTool** — Ya está en el paso 3

Cada herramienta:
- Clase separada con método `execute(params) -> ToolResult`
- Registrada en `ConversationalToolManager.__init__`
- Mapeada en `_execute_command()` de `api.py`

### Verificación:
- "cuánta RAM queda" → SystemInfoTool
- "muéstrame el archivo X" → FileReadTool
- "lista los archivos en /tmp" → FileListTool
- "cuánto es 2+2" → CalculatorTool

---

## Paso 6 — Seguimiento + Streaming errors + Fuentes (2h)

**Riesgo:** Medio-Bajo.

### 6a. Follow-up suggestions (30 min)
- En `_build_system_prompt()`:
```python
system_prompt += " Al final, si es útil, sugiere 1 pregunta de seguimiento breve."
```

### 6b. Streaming errors estructurados (20 min)
- En `api.py` streaming path:
```python
except Exception as exc:
    yield StreamEvent("error", {"type": type(exc).__name__}).to_sse()
```

### 6c. Citas de fuentes en web search (1h)
- En `_enrich_prompt()`, cuando hay resultados web, añadir al prompt:
```
"Cuando uses información de la web, cita la fuente diciendo 'Según [título]...'"
```

### 6d. Más idiomas (30 min)
- En `motor/assistant/language.py`:
  - Añadir lexicones francés y catalán (~20 palabras clave cada uno)

---

## Resumen de Archivos a Modificar

| Archivo | Cambios |
|---------|---------|
| `motor/assistant/api.py` | Pasos 1a, 1b, 3 (mapping), 4 (nuevo endpoint), 6a, 6b, 6c |
| `motor/assistant/intent.py` | Paso 2 (expandir patrones) |
| `motor/assistant/executor.py` | Paso 3 (DateTimeTool) + Paso 5 (5-7 tools) |
| `motor/assistant/language.py` | Paso 6d (más lexicones) |

---

## Orden Seguro de Ejecución

```
Paso 1a → 1b → 2 → 3 → 4 → 5 → 6a → 6b → 6c → 6d
(Bajo riesgo)                              (Medio riesgo)
```

Cada paso se verifica individualmente antes de pasar al siguiente.
