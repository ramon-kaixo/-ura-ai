# Lo que un experto en IA conversacional te aconsejaría

## Análisis sincero del sistema actual

Has construido **toda la infraestructura conversacional**: contexto, intención, estilo, interrupciones,
sentimiento, feedback, memoria episódica, aprendizaje de correcciones, tareas proactivas.
Eso es más del 90% del trabajo que la mayoría de proyectos nunca llegan a hacer.

Pero hay **5 cosas que un experto señalaría como prioritarias**, ordenadas por impacto:

---

## 1. 🚨 El sistema nunca habla con un LLM real

**Estado actual:** Toda la arquitectura conversacional existe, pero las respuestas son
`"¡Hola! ¿En qué puedo ayudarte?"` — texto hardcodeado. Nunca llama a un modelo.

**Lo que haría un experto:**

```python
# En lugar de:
reply = "¡Hola! ¿En qué puedo ayudarte?"

# Hacer:
messages = conversation_engine.build_prompt(cid, mode)
response = model_router.chat(messages, model="respuesta_rapida")
reply = response.content
```

**Impacto:** Pasar de "demo" a "funcional". Sin esto, el resto no importa.
**Esfuerzo:** 2-3h (conectar con `motor/core/llm/router.py` que ya existe).
**Prioridad:** 🔴 INMEDIATA.

---

## 2. 📊 No hay forma de medir si funciona

**Estado actual:** 119 tests, pero ninguno mide calidad de conversación.
No hay métricas de satisfacción, tasa de correcciones, abandonos, repeticiones.

**Lo que haría un experto:**

| Métrica | Cómo medirla | Qué indica |
|---------|-------------|------------|
| **Tasa de reformulación** | ImplicitFeedback ya detecta "was_unclear" | Claridad de las respuestas |
| **Tasa de corrección** | CorrectiveLearning.record_correction | Precisión del conocimiento |
| **Sentimiento promedio** | SentimentDetector score trend | Satisfacción general |
| **Tareas completadas** | ProactiveMemory | Utilidad real |
| **Tasa de interrupción** | InterruptionSystem | Fluidez del diálogo |

**Impacto:** Saber si las mejoras realmente mejoran algo.
**Esfuerzo:** 1h (los datos ya se recogen, solo falta agregarlos).
**Prioridad:** 🟡 ALTA.

---

## 3. 🎯 Usar el modelo correcto para cada cosa

**Estado actual:** Un solo LLM para todo (el que esté configurado).

**Lo que haría un experto:**

| Tarea | Modelo recomendado | GX10 tiene |
|-------|-------------------|------------|
| Clasificar intención | 7B (qwen2.5:7b) ✅ | Sí |
| Responder rápido | 7B o 14B ✅ | Sí |
| Explicación profunda | 32B (qwen3:32b) ✅ | Sí |
| Código complejo | 32B coder ✅ | Sí |
| Embeddings | nomic-embed-text ✅ | Sí |
| Moderación/seguridad | 3B (llama3.2:3b) ✅ | Sí |

Ya tienes los modelos en Ollama. Solo falta que el sistema elija automáticamente:
- Intención simple → modelo pequeño (rápido, barato)
- Pregunta profunda → modelo grande (preciso, caro)
- La primera respuesta siempre en pequeño. Si el usuario pide "explícame más", entonces grande.

**Impacto:** Velocidad ×10 en el 80% de las respuestas.
**Esfuerzo:** 3-4h (conectar con el Model Router existente en `motor/core/llm/router.py`).
**Prioridad:** 🟡 ALTA.

---

## 4. 🛡️ Guardrails de seguridad

**Estado actual:** Cero. No hay filtro de contenido, no hay detección de alucinaciones,
no hay moderación, no hay límites de lo que el asistente puede decir o hacer.

**Lo que haría un experto:**

1. **Frase de sistema obligatoria:** `"Eres un asistente útil. No generes contenido dañino."`
2. **Moderación en cascada:** Modelo pequeño de seguridad (3B) + LLM principal
3. **Detección de alucinaciones:** Si el conocimiento no está en el context, decirlo
4. **Límites de herramientas:** No ejecutar comandos sin confirmación
5. **Auditoría:** Todas las conversaciones registradas (MessageStore ya lo hace)

**Impacto:** Evitar que el asistente haga o diga algo que no deba.
**Esfuerzo:** 4-5h.
**Prioridad:** 🟡 ALTA.

---

## 5. 🌐 Evaluación con usuarios reales

**Estado actual:** Sistema construido en laboratorio, sin usuarios reales.

**Lo que haría un experto:**

1. **Poner el endpoint `/api/v1/chat` detrás de un proxy** (ya existe)
2. **Añadir logging de todas las interacciones** (MessageStore ya lo hace)
3. **Dashboards semanales** con métricas de uso
4. **Bucle de mejora continua:**
   - Semana 1: Recoger datos
   - Semana 2: Identificar problemas
   - Semana 3: Implementar mejoras
   - Repetir

**Impacto:** Mejora basada en datos reales, no en suposiciones.
**Esfuerzo:** 2-3h (los datos ya se recogen).
**Prioridad:** 🟢 MEDIA.

---

## Resumen para el experto

| # | Qué | Impacto | Esfuerzo | Prioridad |
|---|-----|---------|----------|-----------|
| 1 | Conectar con LLM real | 🔥 Crítico | 2-3h | 🔴 Hoy |
| 2 | Métricas de conversación | 📊 Alto | 1h | 🟡 Esta semana |
| 3 | Multi-modelo según tarea | ⚡ Alto | 3-4h | 🟡 Esta semana |
| 4 | Guardrails de seguridad | 🛡️ Alto | 4-5h | 🟡 Esta semana |
| 5 | Evaluación con usuarios | 🌐 Medio | 2-3h | 🟢 Próxima semana |

**El consejo más importante:** Conecta el sistema a un LLM real. Todo lo demás
(interrupciones, sentimiento, feedback, memoria) es potente pero **inútil sin un cerebro
detrás**. Tienes los modelos en GX10, tienes el Model Router, tienes la infraestructura.
Falta el cableado final.

Literalmente, cambias 2 líneas de `api.py` y pasas de respuestas hardcodeadas a
un asistente conversacional real con toda la inteligencia de F29 + F29.5 + F29.6.
