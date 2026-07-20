# Plan Completo — Sistema Conversacional URA

## Estado Actual (28 archivos, 97 tests, desplegado en GX10:8003)

| Dimensión | Estado |
|-----------|--------|
| Motor conversacional | ✅ Completo |
| Intención (12 tipos) | ✅ Completo |
| Contexto 3 niveles | ✅ Completo |
| Memoria vectorial | ✅ Completo |
| Herramientas reales | ✅ Parcial (git, docker, datetime, file, calc, notes, system) |
| Web search | ✅ Completo |
| RAG (Knowledge Engine) | ✅ Completo |
| Streaming | ✅ Completo |
| Multi-idioma | ✅ 4 idiomas (es, en, fr, ca) |
| Moderación | ✅ Completo |
| Auth | ✅ Configurable |
| Feedback | ✅ Endpoint + implícito |
| Evaluación | ✅ Completo |
| Backup | ✅ Script |
| CI/CD | ✅ GitHub Actions configurado |

---

## LO QUE FALTA — Plan de Implementación Completo

### 🔴 FASE 1 — Infraestructura (4h)
*Hace robusto lo que ya existe*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 1.1 | Unificar 6 SQLite DBs en 1 | message_store, corrections, feedback, proactive, vector_memory, evaluation | 2h | Hoy cada subsistema tiene su propia BD. Unificar en `ura.db` con tablas separadas |
| 1.2 | Connection pool / WAL persistente | message_store.py | 1h | Todas las conexiones SQLite usen WAL y pooling |
| 1.3 | Timeout configurables por herramienta | executor.py | 30min | Cada tool con su timeout, no uno global |
| 1.4 | Logging estructurado en todas las tools | executor.py | 30min | Que cada tool registre éxito/fallo/duración |

### 🔴 FASE 2 — Experiencia de Usuario (6h)
*Cosas que el usuario nota en los primeros 5 minutos*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 2.1 | Streaming real token a token via Ollama | llm_bridge.py | Ya hecho | ✅ |
| 2.2 | Recordar el último tema al reconectar | conversation.py | 2h | Cuando el usuario vuelve tras horas, el asistente resume lo último que hablaron |
| 2.3 | Detectar cambio de idioma en mitad de conversación | language.py, conversation.py | 1h | Si el usuario cambia de idioma, el asistente cambia automáticamente |
| 2.4 | "No sé" detection + fallback graceful | api.py, intent.py | 1h | Si el LLM no está seguro, que lo diga explícitamente en vez de alucinar |
| 2.5 | Confirmación antes de acciones destructivas | api.py, executor.py | 1h | Antes de ejecutar "rm -rf", "git push --force", etc., preguntar "¿Seguro?" |
| 2.6 | Memoria de conversaciones cruzadas | conversation.py | 1h | Que recuerde lo que hablaste en otra conversación sobre el mismo tema |

### 🟡 FASE 3 — Herramientas Avanzadas (8h)
*Convierten el asistente de chat a herramienta de trabajo*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 3.1 | Git avanzado (commit, branch, merge) | executor.py | 2h | Poder hacer commits, crear ramas, mergear desde el chat |
| 3.2 | Docker avanzado (exec, build, compose) | executor.py | 2h | Ejecutar comandos en contenedores, buildear imágenes |
| 3.3 | Sistema de archivos completo (cp, mv, find, grep) | executor.py | 2h | Operaciones de archivos con whitelist y confirmación |
| 3.4 | APIs externas (clima, noticias, tipo de cambio) | executor.py | 2h | Consultar APIs públicas con formato amigable |
| 3.5 | Plugin system para tools | tools/, registry.py | 4h | Sistema de plugins para que cualquiera añada tools sin modificar executor.py |

### 🟡 FASE 4 — Conocimiento y Memoria (6h)
*Hacen que el asistente sea más inteligente*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 4.1 | RAG con el Knowledge Engine real | rag.py | 2h | Hoy RAGContext es un stub. Conectarlo a `knowledge/engine/` de verdad |
| 4.2 | Resúmenes automáticos de conversaciones largas | management.py, api.py | 1h | Cuando una conversación supera N turnos, se resume automáticamente |
| 4.3 | Búsqueda semántica en notas guardadas | executor.py (NoteTool) | 1h | Las notas guardadas se indexan con embeddings y se pueden buscar |
| 4.4 | Corrections learning conectado al prompt | api.py, corrective_learning.py | 1h | Cuando corriges algo, se inyecta en el prompt la próxima vez que preguntes |
| 4.5 | Preferencias de usuario conectadas al prompt | api.py, preferences.py | 1h | Modo preferido, longitud, formato se aplican automáticamente |

### 🟢 FASE 5 — UI y Acceso (6h)
*Hacen el sistema accesible desde cualquier parte*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 5.1 | Endpoint WebSocket para chat bidireccional | api.py | 2h | WebSocket en vez de HTTP polling para latencia mínima |
| 5.2 | CLI interactivo (ura chat) | new: cli/assistant_cli.py | 2h | `ura chat` desde terminal con colores y streaming |
| 5.3 | Compartición de conversaciones | api.py | 1h | Generar link público a una conversación |
| 5.4 | Exportar conversación (JSON, TXT, MD) | api.py | 1h | Descargar historial de conversación |

### 🟢 FASE 6 — Calidad y Mantenimiento (4h)
*Aseguran que el sistema mejore con el tiempo*

| # | Tarea | Archivos | Esfuerzo | Descripción |
|---|-------|----------|----------|-------------|
| 6.1 | Tests de integración automáticos | tests/test_integration_assistant.py | 1h | Tests que llaman al endpoint real y verifican respuestas |
| 6.2 | Benchmark de latencia por modelo | new: benchmark_assistant.py | 1h | Medir tiempos de respuesta por modelo y herramienta |
| 6.3 | Dashboard de métricas de conversación | evaluation.py | 1h | Endpoint /metrics con tasas de éxito, satisfacción, correcciones |
| 6.4 | Limpieza automática de conversaciones antiguas | message_store.py | 1h | Borrar conversaciones > N días automáticamente |

---

## RESUMEN

| Fase | Área | Esfuerzo | Prioridad |
|------|------|----------|-----------|
| F1 | Infraestructura | 4h | 🔴 Alta |
| F2 | Experiencia de usuario | 6h | 🔴 Alta |
| F3 | Herramientas avanzadas | 8h | 🟡 Media |
| F4 | Conocimiento y memoria | 6h | 🟡 Media |
| F5 | UI y Acceso | 6h | 🟢 Baja |
| F6 | Calidad | 4h | 🟢 Baja |
| **Total** | | **34h** | |

**Orden de ejecución recomendado:** F2 → F4 → F1 → F3 → F5 → F6

Las fases F2 (experiencia) y F4 (conocimiento) son las que más impacto tienen en el usuario con menor esfuerzo.
