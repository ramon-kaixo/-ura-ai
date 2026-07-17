# ADR-027-01: Modelo de Agentes

**Estado:** Borrador (pendiente de aprobación)  
**Fase:** F27-B1  
**Depende de:** F25 (v0.25.0-fase25), F26 (v0.26.0-rc1), F26.5 (Platform Readiness)

---

## 1. ¿Qué es un agente?

Un **agente** es un programa autónomo que:
- Recibe un objetivo (task)
- Planifica pasos para alcanzarlo (plan)
- Ejecuta los pasos usando herramientas y APIs oficiales
- Consulta conocimiento (F25) y memoria (F26) exclusivamente vía contratos
- Registra su ejecución completa para auditoría
- Finaliza al completar, fallar, o ser cancelado

### ¿Qué NO es un agente?

- ❌ NO es un propietario del conocimiento
- ❌ NO es un sustituto del pipeline de fusión (F25)
- ❌ NO es un escritor directo de Facts
- ❌ NO es un administrador del sistema
- ❌ NO es un intérprete de código arbitrario
- ❌ NO es un planificador global (solo planifica su propia tarea)

### Responsabilidad única

**Recibir un objetivo, planificar su ejecución, ejecutar dentro de los límites de autonomía concedidos, y registrar todo para auditoría.**

---

## 2. Modelo de Dominio

### Agent

```python
@dataclass
class Agent:
    agent_id: str
    capabilities: set[AgentCapability]  # permisos explícitos
    policy: AgentPolicy                 # límites de autonomía
    state: AgentState                   # CREATED | PLANNING | READY | ...
    created_at: float
    parent_id: str | None               # agente que lo creó (si es subagente)
```

Propietario: F27

### AgentTask

```python
@dataclass(frozen=True)
class AgentTask:
    task_id: str
    objective: str          # objetivo en lenguaje natural
    context: AgentContext   # contexto de ejecución
    max_steps: int = 10
    created_at: float
```

Propietario: F27 (quien envía la tarea)

### AgentPlan

```python
@dataclass(frozen=True)
class AgentPlan:
    plan_id: str
    steps: tuple[PlanStep, ...]
    immutable: bool = False  # True = no replanificar
```

Propietario: Planner

### PlanStep

```python
@dataclass(frozen=True)
class PlanStep:
    step_id: str
    action: str              # "retrieve" | "search" | "fetch" | "tool" | "llm" | "message" | "spawn"
    params: dict
    depends_on: tuple[str, ...]  # step_ids que deben completarse antes
```

Propietario: Planner

### AgentContext

```python
@dataclass
class AgentContext:
    conversation: list[dict]     # historial conversacional
    knowledge_facts: list[str]   # fact_ids consultados
    memory_entries: list[str]    # entry_ids de memoria consultados
    plan: AgentPlan | None       # plan actual
    execution_state: dict        # estado intermedio de ejecución
```

Propietario: Executor

### AgentState

```python
class AgentState(StrEnum):
    CREATED = "created"
    PLANNING = "planning"
    READY = "ready"
    RUNNING = "running"
    WAITING = "waiting"      # esperando herramienta/LLM/subagente
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"
```

### AgentResult

```python
@dataclass(frozen=True)
class AgentResult:
    agent_id: str
    task_id: str
    state: AgentState
    output: str
    steps_completed: int
    duration_ms: float
    cost_units: int
    audit: AgentAuditRecord
```

### AgentCapability

```python
class AgentCapability(StrEnum):
    MEMORY_READ = "memory.read"
    MEMORY_WRITE = "memory.write"
    FACTS_READ = "facts.read"
    WEB_SEARCH = "web.search"
    WEB_FETCH = "web.fetch"
    TOOLS_EXECUTE = "tools.execute"
    AGENTS_SPAWN = "agents.spawn"
    AGENTS_MESSAGE = "agents.message"
    CONFIG_READ = "config.read"
```

### AgentPolicy

```python
@dataclass
class AgentPolicy:
    max_duration_seconds: int = 300
    max_cost_units: int = 1000
    max_llm_calls: int = 50
    max_tool_calls: int = 20
    max_plan_depth: int = 5
    max_subagents: int = 3
    timeout_per_step: int = 60
    cancel_on_timeout: bool = True
    retry_max_attempts: int = 3
    backoff_base_seconds: float = 1.0
```

### AgentExecution

```python
@dataclass
class AgentExecution:
    """Estado mutable de una ejecución en curso."""
    agent: Agent
    task: AgentTask
    plan: AgentPlan | None
    context: AgentContext
    current_step: int = 0
    start_time: float = 0.0
    llm_calls: int = 0
    tool_calls: int = 0
    cost_units: int = 0
    cancelled: bool = False
```

### AgentAuditRecord

```python
@dataclass(frozen=True)
class AgentAuditRecord:
    agent_id: str
    task_id: str
    objective: str
    plan: list[str]
    capabilities_used: list[str]
    tools_used: list[str]
    facts_consulted: list[str]
    memory_consulted: list[str]
    llm_calls: int
    decisions: list[dict]
    result: str
    state: str
    duration_ms: float
    cost_units: int
    error: str | None
    timestamp: float
    parent_agent: str | None
```

---

## 3. Ciclo de Vida

```
CREATED ──→ PLANNING ──→ READY ──→ RUNNING ──→ COMPLETED
                              │          │
                              │          ├──→ FAILED
                              │          ├──→ CANCELLED
                              │          └──→ TIMEOUT
                              │
                              └──→ CANCELLED (antes de ejecutar)
```

### Transiciones Válidas

| Desde | Hasta | Condición |
|-------|-------|-----------|
| CREATED | PLANNING | Task asignada, capabilities verificadas |
| PLANNING | READY | Plan generado exitosamente |
| PLANNING | FAILED | No se pudo generar un plan |
| READY | RUNNING | Plan aprobado, recursos disponibles |
| READY | CANCELLED | Cancelación solicitada antes de ejecutar |
| RUNNING | WAITING | Paso en curso (herramienta/LLM) |
| WAITING | RUNNING | Paso completado, continuar con el siguiente |
| RUNNING | COMPLETED | Todos los pasos ejecutados exitosamente |
| RUNNING | FAILED | Error irrecuperable en un paso |
| RUNNING | CANCELLED | Cancelación solicitada durante ejecución |
| RUNNING | TIMEOUT | Excedido max_duration_seconds o timeout_per_step |
| CUALQUIERA | CANCELLED | Cancelación externa siempre posible |

### Transiciones Inválidas

| Desde | Hasta | Motivo |
|-------|-------|--------|
| COMPLETED | RUNNING | No se puede reanudar una ejecución ya completada |
| CANCELLED | RUNNING | No se puede reanudar una ejecución cancelada |
| FAILED | RUNNING | Debe crearse una nueva tarea |
| CREATED | RUNNING | Debe pasar por PLANNING y READY |

---

## 4. Modelo de Ejecución

### Cola y Prioridades

- **Estructura:** `PriorityQueue[AgentExecution]`
- **Prioridades:**
  1. `CRITICAL` — tareas del sistema (auditoría, supervisión)
  2. `HIGH` — tareas de usuario con respuesta esperada
  3. `NORMAL` — tareas de usuario sin presión temporal
  4. `LOW` — tareas background (mantenimiento, exploración)
- **Máximo de agentes concurrentes:** configurable (defecto: 5)

### Reintentos

- Máximo 3 reintentos por paso
- Backoff exponencial: base 1s, multiplicador 2, máximo 30s
- Se reintenta solo si el error es transitorio (timeout, herramienta no disponible)
- Errores permanentes (permiso denegado, tarea inválida) → FAILED sin reintento

### Cancelación

- Cooperativa: el agente verifica `self._cancelled` entre pasos
- Forzosa: si el agente no responde en `timeout_per_step`, se termina el hilo
- En cascada: cancelar un agente padre cancela todos sus subagentes

### Timeouts

| Timeout | Valor | Consecuencia |
|---------|-------|-------------|
| `max_duration_seconds` | 300s | TIMEOUT, auditoría registrada |
| `timeout_per_step` | 60s | Paso marcado como fallido, se reintenta o se cancela |
| LLM call | 30s | Reintento automático (máx 3) |
| Tool call | 30s | Reintento automático (máx 3) |

---

## 5. Capacidades

Cada capacidad se define como un permiso explícito con operaciones permitidas y prohibidas:

| Capacidad | Operaciones permitidas | Operaciones prohibidas | Condiciones |
|-----------|----------------------|----------------------|-------------|
| `memory.read` | `MemoryTimeline.state_at()`, `by_entity()`, `by_time()` | Acceso directo a journal/snapshot | Solo consulta, sin modificación |
| `memory.write` | `Memory.append()` con `event_type=SYSTEM` | Escribir con `event_type=FACT_ADDED` | Solo eventos de sistema, no Facts |
| `facts.read` | `FactIndex.lookup()`, `lookup_entity()`, `lookup_predicate()` | Acceso directo a FactHistory | Solo consulta |
| `web.search` | `WebPipeline.search()` | Llamar a httpx/requests directamente | Mediación del Tool Runner |
| `web.fetch` | `WebPipeline.fetch()` | Acceso directo a URLs | Mediación del Tool Runner |
| `tools.execute` | Tool Registry: herramientas registradas | Ejecutar código arbitrario | Sandbox obligatorio |
| `agents.spawn` | Crear subagente con capabilities subset | Crear agente sin límites | El subagente hereda capabilities restringidas |
| `agents.message` | Enviar/recibir mensajes via EventBus | Acceso directo a otros agentes | Mensajería asíncrona |
| `config.read` | Leer configuración del sistema | Modificar configuración | Solo lectura |

---

## 6. Integración (Dependencias)

```
Agente (F27)
  │
  ├── Planner (F27)
  │     │
  │     └── LLM (vía motor.core.llm) — para generar plan
  │
  ├── Executor (F27)
  │     │
  │     ├── ContextRetriever (F27)
  │     │     ├── FactIndex.lookup_entity() — F25
  │     │     ├── MemoryTimeline.state_at() — F26
  │     │     └── MemoryTimeline.by_entity() — F26
  │     │
  │     ├── ToolRunner (F27)
  │     │     ├── WebPipeline.search() — F24 (indirecto)
  │     │     ├── WebPipeline.fetch() — F24 (indirecto)
  │     │     └── Tool Registry — F27
  │     │
  │     ├── LLM (vía motor.core.llm) — para generar respuesta
  │     │
  │     └── Memory.append() — F26 (auditoría post-ejecución)
  │
  └── EventBus — F27 (comunicación entre agentes y scheduler)
```

**Ningún acceso directo.** Todo acceso a F25, F26, F24 pasa por los contratos definidos en F26.5.

---

## 7. Modelo de Planificación

### ¿El plan es inmutable?

Por defecto: **sí** (una vez generado, no cambia).

### ¿Puede replanificar?

Sí, bajo estas condiciones:
- Un paso falla y no hay reintento posible
- El contexto cambia significativamente (nueva información disponible)
- El plan original es inviable (recursos insuficientes)

### ¿Cuándo?

- Después de un paso fallido (si `retry_max_attempts` se agotó)
- Si el agente detecta que el plan actual no llevará al objetivo
- Como máximo 2 replanificaciones por tarea

### ¿Qué conserva del plan anterior?

- Los pasos ya completados (no se reejecutan)
- El contexto acumulado
- El objetivo original
- Las consultas a memoria ya realizadas

---

## 8. Gestión de Contexto

### Cuatro contextos separados, sin mezclar:

| Contexto | Contenido | Propietario | Persistencia |
|----------|-----------|-------------|-------------|
| **Ejecución** | Estado interno del agente (paso actual, variables) | Executor | En memoria (volátil) |
| **Conversacional** | Historial de mensajes usuario↔agente | AgentSession | F26 (MemoryEntry por conversación) |
| **Memoria** | Facts (F25) + MemoryEntries (F26) recuperados | ContextRetriever | No persiste (se reconstruye cada vez) |
| **Plan** | Plan actual + steps completados | Planner | Solo mientras dura la ejecución |

### Reglas

- El contexto conversacional se conserva entre invocaciones del agente
- El contexto de ejecución se pierde al finalizar el agente
- El contexto de memoria se reconstruye en cada paso
- El contexto del plan persiste solo durante la ejecución activa

---

## 9. Concurrencia

| Aspecto | Decisión |
|---------|----------|
| **Varios agentes** | Thread pool con límite configurable (defecto: 5) |
| **Varias tareas** | PriorityQueue, una tarea por agente |
| **Aislamiento** | Cada agente tiene su propio `AgentExecution` (sin estado compartido) |
| **Recursos compartidos** | FactIndex (solo lectura, thread-safe). Memory (append con lock). |
| **Política de bloqueo** | Lock por recurso compartido (Memory.append). Sin locks de agente a agente. |
| **Cancelación cooperativa** | `agent.cancel()` establece flag. El agente verifica entre pasos. |
| **Deadlock prevention** | Timeout global de 300s. No hay espera circular (agentes no esperan a otros agentes). |

---

## 10. Observabilidad

### Registro obligatorio por ejecución

| Evento | Cuándo | Datos |
|--------|--------|-------|
| `agent.created` | Creación del agente | agent_id, task_id, capabilities, policy |
| `agent.planning` | Inicio de planificación | objective |
| `agent.plan_ready` | Plan generado | steps, depth |
| `agent.step_start` | Inicio de paso | step_id, action, params |
| `agent.step_complete` | Fin de paso | step_id, duration, result |
| `agent.step_failed` | Paso fallido | step_id, error, attempt |
| `agent.tool_call` | Herramienta invocada | tool_name, params, duration |
| `agent.llm_call` | LLM invocado | prompt_length, response_length, duration |
| `agent.memory_read` | Consulta a memoria | target, results_count |
| `agent.facts_read` | Consulta a Facts | entity, results_count |
| `agent.replan` | Replanificación | reason, steps_before, steps_after |
| `agent.completed` | Finalización exitosa | result, duration, cost |
| `agent.failed` | Fallo | error, duration |
| `agent.cancelled` | Cancelación | reason, duration |
| `agent.timeout` | Timeout | exceeded_limit, duration |

### Almacenamiento

- Todos los eventos se registran en el `AgentAuditRecord`
- El `AgentAuditRecord` se persiste en F26 como `MemoryEntry` al finalizar
- Los eventos en tiempo real se emiten por `EventBus` para dashboards

---

## 11. Recuperación

| Escenario | Comportamiento | Recuperación |
|-----------|---------------|-------------|
| **Caída del proceso** | Todos los agentes en memoria se pierden | Las tareas no completadas se pierden. Las completadas están en F26 (auditoría). |
| **Reinicio del sistema** | Scheduler se reinicia, cola vacía | No hay recuperación de tareas en curso. Auditorías completadas sobreviven en F26. |
| **Tarea interrumpida** | Timeout por max_duration_seconds | AgentState → TIMEOUT. Audit registrado. |
| **Herramienta bloqueada** | Timeout de tool_call (30s) | Reintento (hasta 3). Si persiste, paso fallido. |
| **LLM bloqueado** | Timeout de LLM call (30s) | Reintento (hasta 3). Si persiste, paso fallido. |
| **Plan inviable** | Replanificación (máx 2) | Si no se puede generar plan alternativo → FAILED |

---

## 12. Invariantes

```
A01. Todo agente tiene un agent_id único.
A02. Todo agente tiene capabilities explícitas en su creación.
A03. Un agente nunca ejecuta una operación sin la capability correspondiente.
A04. AgentState sigue las transiciones definidas (no hay saltos inválidos).
A05. Toda ejecución produce un AgentAuditRecord.
A06. Todo AgentAuditRecord se persiste en F26.
A07. Ningún agente modifica Facts (solo lectura).
A08. Ningún agente accede directamente a FactHistory, FactIndex, MemoryTimeline, Journal o Snapshot.
A09. El plan es inmutable por defecto (salvo replanificación explícita).
A10. Máximo 2 replanificaciones por tarea.
A11. Los subagentes heredan un subconjunto de capabilities del padre (nunca ampliado).
A12. La cancelación es siempre posible (cooperativa + forzosa).
A13. El contexto de ejecución no se comparte entre agentes.
A14. Las decisiones del agente son reconstruibles desde el audit record.
```

---

## 13. Métricas

| Métrica | Target | Cómo se mide |
|---------|--------|-------------|
| Planificación (p50) | < 2s | Tiempo desde CREATED → READY |
| Planificación (p99) | < 10s | Tiempo desde CREATED → READY |
| Paso individual (p50) | < 5s | Tiempo por PlanStep |
| Paso individual (p99) | < 30s | Tiempo por PlanStep |
| Throughput | > 10 tareas/min | Tareas COMPLETED / minuto |
| Tasa de éxito | > 80% | COMPLETED / (COMPLETED + FAILED + TIMEOUT) |
| Utilización de herramientas | < 50% | Pasos con tool / total pasos (evitar dependencia excesiva) |
| Coste medio por tarea | < 100 unidades | cost_units / tarea |
| Memoria por agente | < 50 MB | RSS del hilo del agente |
| Tiempo de cancelación | < 1s | Desde cancel() hasta CANCELLED |

---

## 14. Riesgos

| Riesgo | Prob | Impacto | Mitigación |
|--------|------|---------|-----------|
| **Bucles de planificación** | Media | Alto | Máx 2 replanificaciones. Timeout global 300s. |
| **Tormenta de herramientas** | Baja | Alto | `max_tool_calls: 20`. Tool runner con rate limiter. |
| **Crecimiento del contexto** | Alta | Medio | Contexto conversacional con límite de tamaño. Resumen automático. |
| **Starvation** | Baja | Medio | PriorityQueue con aging (tareas LOW suben de prioridad con el tiempo). |
| **Deadlocks** | Baja | Alto | Sin espera circular. Timeout global. Lock único por recurso. |
| **Consumo descontrolado de LLM** | Media | Alto | `max_llm_calls: 50`. Coste monitorizado en tiempo real. |
| **Pérdida de trazabilidad** | Baja | Crítico | `AgentAuditRecord` obligatorio. Persistencia en F26. |
| **Subagente huérfano** | Baja | Medio | Timeout + cancelación en cascada. Watchdog. |

---

## 15. Criterio de Aceptación

F27-B1 se considerará completo cuando:

| # | Criterio | Cómo se verifica |
|---|----------|-----------------|
| 1 | ADR-027-01 aprobado | Revisión arquitectónica |
| 2 | Todos los modelos definidos (13 entidades) | Documento completo |
| 3 | Ciclo de vida formalizado (9 estados, 14 transiciones válidas, 4 inválidas) | Matriz de transiciones |
| 4 | Modelo de ejecución documentado (cola, prioridades, reintentos, cancelación, timeouts) | Especificación |
| 5 | Capacidades formalizadas (9 capacidades) | Tabla operaciones permitidas/prohibidas |
| 6 | Integración con F25/F26 especificada (sin accesos directos) | Diagrama de dependencias |
| 7 | Planificación documentada (inmutabilidad, replanificación, conservación) | Especificación |
| 8 | Contextos separados (4 tipos, sin mezclar) | Especificación |
| 9 | Concurrencia definida (thread pool, locks, cancelación) | Especificación |
| 10 | Observabilidad especificada (15 eventos de auditoría) | Especificación |
| 11 | Recuperación documentada (6 escenarios) | Especificación |
| 12 | 14 invariantes definidos | Lista de invariantes |
| 13 | 9 métricas con target | Tabla de métricas |
| 14 | 8 riesgos identificados con mitigación | Matriz de riesgos |
| 15 | Contratos F25/F26 preservados | Verificación contra G-01 a G-08 |
