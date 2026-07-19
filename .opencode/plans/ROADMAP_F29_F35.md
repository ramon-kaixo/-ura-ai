# Roadmap F29–F35 — Plan de Ejecución

**Baseline actual:** v0.29.0-fase29 (producción ready, CI/CD, cobertura 36%, 0 lint)
**Prerrequisito:** F28.1 estabilizado, F29 Production Readiness cerrado

---

## Resumen de lo que ya tenemos (reutilizar, no tocar)

| Área | Estado | Usar en |
|------|--------|---------|
| **F26 Memory** (Timeline, Journal, Snapshot) | ✅ 96% cobertura | B2 contexto, B9 gestión |
| **F27 Agents** (Planner, Runner, Scheduler, Gate) | ✅ 71-99% cobertura | B5 planificador, B6 orquestador |
| **F28 Protocol** (Envelope, Tracing, Health) | ✅ 74-99% cobertura | Todas las fases |
| **LLM Providers** (Ollama, OpenAI, Anthropic, etc.) | ✅ Funcional | B1 motor, B3 intención |
| **Model Router** | ✅ Producción | B1 motor |
| **ToolRunner + ToolAdapter ABC** | ✅ Framework listo | B6 orquestador |
| **core/mochila/tools.py** (web, file, crawl) | ✅ 4 herramientas | B6 (migrar a motor/) |
| **SessionMemory** (episódica) | ✅ 54% cobertura | B2 contexto |
| **Evaluación (EvaluationEngine, baselines)** | ✅ Framework | F30-B1/B2 |
| **Prometheus, health, métricas** | ✅ Listo | F30-B8 supervisor |
| **CI/CD, 0 lint, requirements limpio** | ✅ Listo | Todas las fases |

---

## F29 — Asistente Conversacional Inteligente (~30h)

**Objetivo:** URA conversa naturalmente, mantiene hilo, entiende intención, elige herramientas.

### B1 — Motor conversacional (6-8h)
Nuevo: `motor/assistant/conversation.py`

| Tarea | Archivos | Depende de |
|-------|----------|------------|
| `ConversationEngine` (turnos, historial, ventana tokens) | `motor/assistant/conversation.py` | F26, SessionMemory |
| Almacén mensajes `{role, content, timestamp}` | `motor/assistant/message_store.py` | — |
| Ventana deslizante con presupuesto de tokens | `motor/assistant/context_window.py` | — |
| Streaming orchestration (tool calls mid-stream) | `motor/assistant/streaming.py` | — |
| Endpoint chat unificado (FastAPI) | `motor/assistant/api.py` | — |

### B2 — Gestor de contexto (4-5h)
Nuevo: `motor/assistant/context.py`

| Componente | Implementación |
|-----------|----------------|
| Contexto inmediato (últimos N turnos) | Cola circular en memoria |
| Contexto conversación | Reutilizar `motor/intelligence/memory/episodic.py:SessionMemory` |
| Memoria histórica (F26) | Reutilizar `motor/memory/` |
| Context assembly con límite de tokens | Algoritmo priority-based truncation |

### B3 — Comprensión de intención (4-5h)
Nuevo: `motor/assistant/intent.py`

| Función | Enfoque |
|---------|---------|
| Clasificador intención | LLM-as-classifier (prompt especializado) |
| Extracción entidades | Regex + LLM combinado |
| Referencias ("eso", "el anterior") | Heurística + contexto inmediato |
| UserIntent → AgentCapability | Mapeo directo enum→enum |

### B4 — Estilo conversacional (2h)
Nuevo: `motor/assistant/style.py` — modos: `conversacion`, `trabajo`, `explicacion`

### B5 — Planificador conversacional (3h)
Wrapper sobre F27 Planner: intención → objetivos → tareas → dependencias → riesgo

### B6 — Orquestador de herramientas (3-4h)
Migrar `core/mochila/tools.py` → `motor/assistant/tools/`. Nuevas: `GitTool`, `DockerTool`, `SSHTool`, `KnowledgeQueryTool`

### B7 — Capa de personalidad (2-3h)
Nuevo: `motor/assistant/personality.py` — `PersonalityConfig` + system prompt templating

### B8 — Aprendizaje conversacional (2h)
Detectar preferencias del usuario (longitud, formato, patrones)

### B9 — Gestión de conversaciones (2h)
Detectar cambio de objetivo, dividir conversaciones largas, resumir, recuperar temas

---

## F30 — Inteligencia Adaptativa (~25h)

**Objetivo:** URA mejora solo.

| Bloque | h | Descripción |
|--------|---|-------------|
| B1 Autoevaluación | 4 | Detectar errores, medir calidad, degradación |
| B2 Drift Detection | 3 | Comportamiento LLM, conocimiento, ranking |
| B3 Autooptimización | 4 | Pesos híbrido, umbrales, estrategias |
| B4 Aprendizaje interno | 3 | Qué búsquedas/planes/herramientas funcionan |
| B5 Reindexación Δ | 2 | Solo recalcular vectores cambiados |
| B6 Benchmark continuo | 2 | EvaluationEngine + baselines históricos |
| B7 Recomendador | 2 | URA propone mejoras, refactor, limpieza |
| B8 Supervisor | 3 | Rendimiento, memoria, errores, agentes, tools |

---

## F31 — Escalabilidad (15-25h)
Distribuido, scheduler persistente, cachés, paralelización, RAM optimizada, millones de docs.

## F32 — Seguridad Enterprise (15-20h)
RBAC, ACL, auditoría, cifrado E2E, sandbox docker, secretos, aislamiento agentes.

## F33 — Studio (25-40h)
GUI web: editor agentes/pipelines, inspector memoria/conocimiento, monitorización.

## F34 — Ecosistema (20-30h)
SDK, marketplace, plugins firmados, dependencias, versionado.

## F35 — Investigación (continua)
Graph RAG, Hybrid Reasoning, Memory Graphs, Multimodal Fusion, Online Learning.

---

## Dependencias

```
F29 (Conversación) ──→ F30 (Adaptativa) ──→ F31 (Escalabilidad)
      │                                            │
      ├──→ F33 (Studio) ───────────────────────────┤
      │                                            │
      └──→ F34 (Ecosistema) ───────────────────────┘
                       │
                       └──→ F35 (Investigación)
                                   
F32 (Seguridad) ──→ Puede empezar en paralelo a F31
```

## Orden Recomendado

1. **F29 B1-B3** (Motor + Contexto + Intención) — 15-18h
2. **F29 B4-B6** (Estilo + Planificador + Herramientas) — 8-10h
3. **F29 B7-B9** (Personalidad + Aprendizaje + Gestión) — 6-7h
4. **F30** (Adaptativa) — 20-30h
5. **F31 + F32** (Escalabilidad + Seguridad) — 30-45h (paralelo)
6. **F33** (Studio) — 25-40h
7. **F34** (Ecosistema) — 20-30h
8. **F35** (Investigación) — continua

**Estimación total F29-F35:** ~160-250h
