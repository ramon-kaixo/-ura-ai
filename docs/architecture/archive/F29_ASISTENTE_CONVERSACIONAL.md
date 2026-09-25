# F29 — Asistente Conversacional Inteligente

**Estado:** ✅ Completo (v0.29.0-fase29 + 7 commits adicionales)
**Fecha:** 2026-07-19
**Tags:** `v0.29.0-fase29`, commits `3003dd9` a `ba40668`
**Tests:** 119 tests, 0 lint, 0 regresiones
**Arquitectura:** `motor/assistant/` (16 archivos)

---

## Resumen

Se ha construido un motor conversacional completo para URA, transformando el sistema de un
framework de agentes basado en comandos a un asistente con el que se conversa de forma natural.
El sistema entiende intención, mantiene contexto, adapta su estilo, planifica acciones,
ejecuta herramientas, y aprende de las interacciones.

---

## Arquitectura

```
Usuario
   │
   ▼
┌──────────────────────────────┐
│         api.py               │  FastAPI /api/v1/chat
│   ChatRequest → Response     │
└──────────┬───────────────────┘
           │
┌──────────▼───────────────────┐
│     conversation.py          │  ConversationEngine
│  • Turnos e historial        │
│  • Detección de intención    │
│  • Resolución de referencias │
└──────┬──────┬──────┬─────────┘
       │      │      │
┌──────▼─┐ ┌──▼──┐ ┌▼─────────┐
│ intent │ │style│ │planner   │
│ .py    │ │.py  │ │.py       │
│ Clasi- │ │3    │ │Objetivos │
│ ficador│ │modos│ │Tareas    │
│ Entida-│ │     │ │Riesgos   │
│ des    │ │     │ │Next act. │
└────────┘ └─────┘ └────┬─────┘
                        │
              ┌─────────▼──────────┐
              │     tools.py       │
              │  ToolOrchestrator  │
              │  Git, Shell, etc.  │
              └────────────────────┘

┌──────────────────────────────────┐
│          context.py              │  ContextManager
│  • Nivel 1: Contexto inmediato   │
│  • Nivel 2: Historial conversac. │
│  • Nivel 3: Memoria histórica F26│
│  • Prioridad + TTL + Score       │
└──────────────────────────────────┘

┌──────────┐ ┌──────────┐ ┌────────────┐
│personali │ │learning  │ │management  │
│ty.py     │ │.py       │ │.py         │
│Decide:   │ │SQLite    │ │Metas       │
│resumir   │ │preferen. │ │Resúmenes   │
│preguntar │ │por usu.  │ │Tareas pend.│
│asumir    │ │          │ │Split conv. │
└──────────┘ └──────────┘ └────────────┘
```

---

## Componentes por Bloque

### B1 — Motor Conversacional (6 archivos, 30 tests)

| Archivo | Propósito | Clase principal | Métodos clave |
|---------|-----------|-----------------|---------------|
| `models.py` | Modelos de datos | `Message`, `Conversation`, `ConversationState`, `UserIntent`, `ConversationMode` | — |
| `message_store.py` | Persistencia SQLite | `MessageStore` | `append()`, `get_conversation()`, `list_conversations()`, `delete_conversation()` |
| `context_window.py` | Ventana con presupuesto de tokens | `ContextWindow` | `build_context()`, `trim_to_budget()` |
| `conversation.py` | Lógica conversacional central | `ConversationEngine` | `create_conversation()`, `add_message()`, `get_context()`, `detect_intent()`, `resolve_reference()` |
| `streaming.py` | Orquestación SSE | `StreamManager` | `stream_response()`, `build_tool_call_event()` |
| `api.py` | Endpoint FastAPI | `router` (`/api/v1/chat`) | `chat()`, `list_conversations()`, `delete_conversation()` |

**Flujo básico:**
```
POST /api/v1/chat { message, conversation_id, mode }
  → ConversationEngine.get_or_create(cid)
  → IntentEngine.classify(message) → UserIntent
  → ContextManager.assemble(cid) → context messages
  → add_message("user", message)
  → generar respuesta según modo/intent
  → add_message("assistant", reply)
  → ChatResponse { conversation_id, reply, intent, turn_count }
```

### B2 — Gestor de Contexto (1 archivo, 17 tests)

| Componente | Implementación |
|-----------|----------------|
| **ContextLevel** | Enum con 3 niveles: IMMEDIATE(3), CONVERSATION(2), HISTORICAL(1) |
| **ContextItem** | Dataclass con content, level, source, priority, ttl_seconds, score |
| **ContextManager** | `assemble()` con fusión ponderada por score + expiración |
| **HistoricalMemoryAdapter** | Bridge a F26 Memory (`motor/memory/`) |

**Prioridades:**
- Contexto inmediato: score = priority(1.0) × level(3) = 3.0
- Historial conversación: score = priority(0.7) × level(2) = 1.4
- Memoria histórica: score = priority(0.5) × level(1) = 0.5

### B3 — Comprensión de Intención (1 archivo, 26 tests)

| Función | Enfoque |
|---------|---------|
| **Clasificación** | Regex por patrón (11 intents) con confianza asociada (0.5-0.95) |
| **Extracción entidades** | 8 patrones: url, email, número, fecha, ruta, idioma, search_query, filename |
| **Routing** | `intent_to_capability()`: COMMAND → tools_execute, QUESTION → knowledge_query |
| **Referencias** | "eso", "el anterior", "hazlo", "como antes" resueltas con contexto |
| **Confianza** | 0.95 para saludos/despedidas, 0.8-0.85 para preguntas/comandos, 0.5 para chat |

**Intents soportados:** `CHAT`, `QUESTION`, `COMMAND`, `SEARCH`, `CLARIFY`, `GREETING`, `FAREWELL`, `CONFIRM`, `REJECT`, `CORRECT`, `REPEAT`, `UNKNOWN`

### B4 — Estilo Conversacional (1 archivo, 14 tests)

| Modo | Tone | Formality | Longitud | Bullets | Emojis | Profundidad |
|------|------|-----------|----------|---------|--------|-------------|
| `conversacion` | casual | informal | 500 chars | ❌ | ✅ | shallow |
| `trabajo` | professional | formal | 1500 chars | ✅ | ❌ | normal |
| `explicacion` | didactic | neutral | 2000 chars | ✅ | ❌ | deep |

**Intent overrides:** Greeting → 200 chars, Command → bullets, Question → deep + ejemplos.

### B5 — Planificador Conversacional (1 archivo, 11 tests)

| Función | Descripción |
|---------|-------------|
| `create_plan()` | Genera objetivo, tareas, riesgos y siguiente acción según intent + modo |
| `get_plan()` / `update_plan()` | CRUD de planes |
| `assess_risks()` | Riesgos predefinidos por intent (ambigüedad, permisos, info incompleta) |
| `_determine_next_action()` | Acción sugerida según intent (buscar, ejecutar, preguntar, reformular) |

### B6 — Orquestador de Herramientas (1 archivo, 6 tests)

| ToolAdapter | Comando | Método |
|-------------|---------|--------|
| `GitStatusTool` | `git status --short` | Estado del repo |
| `GitLogTool` | `git log --oneline -n` | Historial de commits |
| `ShellTool` | shell=False con lista | Comandos arbitrarios |

**ToolOrchestrator:** Selecciona herramienta según intent + entidades.
Extensible via `register()`.

### B7 — Capa de Personalidad (1 archivo, 8 tests)

| Decisión | Cuándo | Condición |
|----------|--------|-----------|
| **Resumir** | Texto largo (>300 chars) y no es saludo/despedida | `should_summarize()` |
| **Preguntar** | Confianza baja (<0.6) y intent ambiguo | `should_ask()` |
| **Asumir** | Confianza alta (>0.8) y es comando | `should_assume()` |

### B8 — Aprendizaje Conversacional (1 archivo, 3 tests)

| Función | Descripción |
|---------|-------------|
| `record_interaction()` | Guarda intent, longitud, modo, éxito en SQLite |
| `get_preferences()` | Retorna preferencias calculadas: longitud, formato, modo, intents previos |
| `_load_preferences()` | Calcula promedio de longitud y modo más frecuente |

### B9 — Gestión de Conversaciones (1 archivo, 9 tests)

| Función | Descripción |
|---------|-------------|
| `detect_goal_change()` | Detecta cambio de objetivo entre turnos |
| `needs_summary()` | Activa resumen automático tras N mensajes (default 50) |
| `split_conversation()` | Divide conversación larga en dos |
| `add_pending_task()` | Registra tarea pendiente asociada a conversación |
| `get_pending_tasks()` | Recupera tareas pendientes |

---

## Cómo Empezar a Usarlo

```python
from motor.assistant.conversation import ConversationEngine
from motor.assistant.intent import IntentEngine
from motor.assistant.context import ContextManager
from motor.assistant.style import StyleEngine
from motor.assistant.planner import ConversationalPlanner
from motor.assistant.tools import ToolOrchestrator

# Motor conversacional
engine = ConversationEngine()
msg = engine.add_message("conv1", "user", "busca información sobre IA")
intent = engine.detect_intent("busca información sobre IA")
print(intent)  # UserIntent.COMMAND

# Clasificación de intención
intent_engine = IntentEngine()
result = intent_engine.classify("qué es URA?")
print(result.intent, result.confidence, result.entities)

# Contexto
ctx = ContextManager()
context = ctx.assemble("conv1")

# Estilo
style = StyleEngine()
profile = style.get_profile(ConversationMode.WORK, UserIntent.COMMAND)
prompt = style.build_system_prompt(ConversationMode.WORK)
```

---

## Consistencia con el Roadmap General

| Fase | Depende de | Estado |
|------|-----------|--------|
| F25 Knowledge Fusion | — | ✅ Cerrada |
| F26 Historical Memory | — | ✅ Cerrada |
| F27 Autonomous Agents | — | ✅ Cerrada |
| F28 Platform Protocols | — | ✅ Cerrada |
| **F29 Conversacional** | F26, F27, F28 | ✅ **Completa** |
| F30 Inteligencia Adaptativa | F29 | Pendiente |

F29 se apoya en F26 (memoria histórica para contexto nivel 3),
F27 (ToolAdapter ABC, AgentPlanner), y F28 (ProtocolEnvelope,
trazabilidad, health checks).

---

## Lo que NO cubre F29 (para fases futuras)

- Integración con LLM real (usar `motor/core/llm/` + Model Router)
- Dashboard web (F33 Studio)
- Seguridad multiusuario (F32)
- Autooptimización (F30)
- Conexión con F24 Knowledge Engine para RAG conversacional
