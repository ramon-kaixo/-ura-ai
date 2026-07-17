# F26.5 — Platform Readiness: Pre-F27 Architecture Review

**Objetivo:** Validar que la plataforma F25+F26 está preparada para ejecutar agentes autónomos (F27) sin romper los contratos establecidos.

---

## 1. Permisos de Agente

### Modelo: Capability-based, no role-based

Cada agente recibe un conjunto explícito de capacidades en su inicialización. No hay permisos implícitos.

| Capacidad | Permiso | Afecta a | Contrato |
|-----------|---------|----------|----------|
| `memory.read` | Leer memoria histórica | F26 | `MemoryTimeline.state_at()`, `by_entity()` |
| `memory.write` | Escribir en memoria | F26 | `Memory.append()` vía `MemoryEntry` |
| `facts.read` | Leer Facts vigentes | F25 | `FactIndex.lookup()`, `lookup_entity()` |
| `facts.write` | NO PERMITIDO | F25 | Los Facts son solo de ida (FusionPipeline → Memoria) |
| `web.search` | Buscar en web | F24 | `WebPipeline.search()` (indirecto) |
| `web.fetch` | Obtener URL | F24 | `WebPipeline.fetch()` (indirecto) |
| `tools.execute` | Ejecutar herramienta | F27 | Tool Registry |
| `agents.spawn` | Crear subagentes | F27 | MultiAgentRuntime |
| `agents.message` | Comunicarse con otros agentes | F27 | Agent Message Bus |
| `config.read` | Leer configuración | Sistema | Solo lectura, sin modificaciones |
| `config.write` | NO PERMITIDO | Sistema | La configuración es inmutable para agentes |

### Reglas

1. Todo agente se crea con `capabilities: set[str]` explícito
2. Una capacidad no listada = denegada
3. Intentar usar una capacidad no concedida → `PermissionError` con trazabilidad
4. Las capacidades se asignan en la creación del agente y no cambian durante su ciclo de vida
5. `facts.write` está prohibido para cualquier agente (los Facts solo los crea FusionPipeline)

---

## 2. Modelo de Ejecución

### Decisión: Asíncrono con Planificador y Cola

| Aspecto | Decisión | Justificación |
|---------|----------|---------------|
| **Naturaleza** | Asíncrono | Los agentes pueden ejecutarse durante segundos/minutos. Bloquear el hilo principal no es aceptable. |
| **Planificación** | Planificador con cola | `PlannerAgent` genera un plan → `ExecutorAgent` ejecuta pasos → resultados retroalimentan al planificador |
| **Comunicación** | Dirigida por eventos | `EventBus` para notificaciones entre agentes. No hay acoplamiento directo. |
| **Jerarquía** | Plana (no árbol fijo) | Un agente supervisor puede crear subagentes, pero la jerarquía es dinámica, no estructural. |
| **Concurrencia** | Un agente por hilo (thread pool) | Cada agente ejecuta en su propio hilo. Límite configurable de hilos concurrentes. |

### Flujo de Ejecución

```
Objetivo (usuario/sistema)
    │
    ▼
PlannerAgent
    │  planifica
    ▼
Plan: [Paso1, Paso2, ...]
    │
    ▼
ExecutorAgent (por paso)
    │
    ├── Retriever (F25 + F26)
    │     │  consulta Facts + Memoria
    │     ▼
    │   Contexto
    │
    ├── Herramientas (opcional)
    │     │  web search, web fetch, tools
    │     ▼
    │   Resultados
    │
    └── LLM (genera respuesta)
          │
          ▼
    Resultado del paso
    │
    ▼
SupervisorAgent
    │  verifica, decide continuar/cancelar
    ▼
Resultado final
    │
    ▼
Memory.append() (F26) — registrar la ejecución
```

---

## 3. Control de Autonomía

### Límites configurables por agente

| Límite | Defecto | Descripción |
|--------|---------|-------------|
| `max_duration_seconds` | 300 | Tiempo máximo de ejecución de un agente |
| `max_cost_units` | 1000 | Coste computacional máximo (LLM calls + tools) |
| `max_llm_calls` | 50 | Número máximo de llamadas a LLM |
| `max_tool_calls` | 20 | Número máximo de invocaciones de herramientas |
| `max_plan_depth` | 5 | Profundidad máxima de planificación |
| `max_subagents` | 3 | Número máximo de subagentes que puede crear |
| `timeout_per_step` | 60 | Timeout por paso individual |
| `cancel_on_timeout` | True | Cancelar todo el plan si un paso excede el timeout |

### Mecanismo de Cancelación

- Cualquier agente puede ser cancelado externamente vía `agent.cancel()`
- La cancelación es cooperativa (el agente debe checkear `self._cancelled`)
- Si un agente no responde a cancelación en `timeout_per_step`, se termina el hilo

### Presupuesto de Coste

El coste se mide en "unidades de cómputo":
- 1 llamada LLM = 10 unidades
- 1 herramienta = 5 unidades
- 1 búsqueda web = 2 unidades
- 1 consulta a memoria = 1 unidad

Cuando se excede `max_cost_units`, el agente debe finalizar su paso actual y detenerse.

---

## 4. Interacción con F25 y F26

### Contratos Estrictos

| Agente quiere... | Debe usar... | NO debe usar... |
|-----------------|-------------|-----------------|
| Leer Facts vigentes | `FactIndex.lookup()`, `lookup_entity()` | Acceso directo a FactHistory |
| Leer memoria histórica | `MemoryTimeline.state_at()`, `by_entity()` | Acceso directo a journal/snapshot en disco |
| Escribir recuerdo de ejecución | `Memory.append()` con `MemoryEntry` | Escribir directamente en FactIndex |
| Buscar información nueva | `WebPipeline.search()` | Llamar a httpx directamente |
| Consultar el LLM | `motor.core.llm.generate()` | Llamar a la API de Ollama directamente |

### Prohibiciones Explícitas

| Operación | Motivo |
|-----------|--------|
| ❌ Modificar Facts existentes | Los Facts son inmutables. Solo FusionPipeline los crea. |
| ❌ Eliminar entries de memoria | La memoria es append-only. |
| ❌ Modificar configuración del sistema | La configuración es inmutable para agentes. |
| ❌ Acceder al sistema de archivos fuera de rutas permitidas | Seguridad. |
| ❌ Ejecutar código arbitrario | Sandbox obligatorio. |

### Flujo de Consulta (Lectura)

```
Agente
  │
  ▼
ContextRetriever (F27)
  │
  ├── FactIndex.lookup_entity(entity)  → Facts vigentes (F25)
  ├── MemoryTimeline.state_at(ts)      → Memoria histórica (F26)
  └── MemoryTimeline.by_entity(entity) → Entradas de memoria relevantes (F26)
  │
  ▼
Contexto consolidado → LLM
```

### Flujo de Escritura (Memoria)

```
Agente
  │
  ▼
Resultado de ejecución
  │
  ▼
MemoryEntry (F26)
  │
  ▼
Memory.append() (F26)
  │
  ▼
Journal + Snapshot (durabilidad)
```

---

## 5. Auditoría de Agentes

### Registro Obligatorio

Cada ejecución de agente debe producir un `AgentAuditRecord`:

```python
@dataclass(frozen=True)
class AgentAuditRecord:
    agent_id: str
    objective: str                  # objetivo original
    plan: list[str]                 # pasos planificados
    tools_used: list[str]           # herramientas invocadas
    facts_consulted: list[str]      # fact_ids consultados
    memory_consulted: list[str]     # memory entry_ids consultados
    decisions: list[dict]           # decisiones intermedias
    result: str                     # resultado final
    termination_reason: str         # completed | cancelled | timeout | error
    duration_ms: float              # duración total
    cost_units: int                 # coste computacional
    timestamp: float                # instante de ejecución
    parent_agent: str | None        # agente padre (si es subagente)
```

### Almacenamiento

Los `AgentAuditRecord` se almacenan en F26 como `MemoryEntry` con:
- `event_type = MemoryEventType.SYSTEM`
- `source = "agent"`
- `fact_refs` con los facts consultados
- `metadata.created_by = agent_id`

### Reconstrucción

Dado un `agent_id`:
1. `MemoryTimeline.by_source("agent")` → todas las ejecuciones de agentes
2. Filtrar por `agent_id` en metadata
3. Cada entry contiene el `AgentAuditRecord` completo

---

## 6. Riesgos Identificados

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|-----------|
| Agente accede directamente a F25/F26 sin contratos | Alta | Crítico | Capability-based permissions + code review |
| Agente escribe Facts directamente | Media | Crítico | `facts.write` prohibido, monitorizado |
| Bucle infinito de planificación | Media | Alto | `max_plan_depth`, `max_duration_seconds`, watchdog |
| Fuga de memoria por subagentes huérfanos | Baja | Alto | Timeout + cancelación en cascada |
| Dos agentes modifican el mismo estado | Baja | Medio | `Memory.append()` es append-only, no hay conflicto |
| Agente ignora la memoria y alucina | Alta | Medio | `ContextRetriever` obligatorio, `facts_consulted` en auditoría |

---

## 7. Criterios para Autorizar F27

| # | Criterio | Cómo se verifica |
|---|----------|------------------|
| 1 | Modelo de permisos implementado | `Agent.__init__` requiere `capabilities` |
| 2 | Ejecución asíncrona con cola | `AgentExecutor` con thread pool |
| 3 | Límites de autonomía configurables | `AgentConfig` con defaults |
| 4 | Contratos F25/F26 respetados | Tests E2E que verifican que agentes usan `FactIndex`/`Memory`, no acceso directo |
| 5 | Auditoría completa por ejecución | `AgentAuditRecord` obligatorio |
| 6 | Cancelación funciona | Test de timeout + cancelación |
| 7 | Sin regresiones en F25+F26 | Suite completa de tests |
