# F27-A1: Auditoría Arquitectónica de Agentes

**Fecha:** 2026-07-17  
**Objetivo:** Revisar arquitectura, no funcionalidad.

---

## 1. Violaciones SRP

| Componente | Responsabilidad | ¿Cumple SRP? |
|-----------|----------------|--------------|
| `AgentOrchestrator` | Coordinar componentes | ✅ Solo orquesta |
| `AgentCapabilityGate` | Autorizar operaciones | ✅ Solo permisos |
| `RuleBasedPlanner` | Generar planes | ✅ Solo planifica |
| `AgentScheduler` | Gestionar cola | ✅ Solo scheduling |
| `AgentToolRunner` | Ejecutar herramientas | ✅ Solo ejecución |
| `AgentStateMachine` | Validar transiciones | ✅ Solo estados |
| `AgentAuditRecord` | Registrar auditoría | ✅ Solo datos |
| `CapabilityGate`, `Planner`, `Scheduler`, `ToolRunner` (ABCs) | Definir contratos | ✅ Solo interfaces |

**Hallazgo:** Ninguna violación SRP detectada.

---

## 2. Dependencias Ocultas

| Archivo | Dependencia | Visible u oculta |
|---------|------------|------------------|
| `agent.py` | `motor.agents.base` (ABCs) | Visible ✅ |
| `gate.py` | `motor.agents.base`, `motor.agents.models` | Visible ✅ |
| `planner.py` | `motor.agents.base`, `motor.agents.models` | Visible ✅ |
| `scheduler.py` | `motor.agents.models` | Visible ✅ |
| `runner.py` | `motor.agents.base`, `motor.agents.models` | Visible ✅ |
| `state.py` | `motor.agents.base`, `motor.agents.models` | Visible ✅ |

**Hallazgo:** No hay dependencias ocultas. Todas son explícitas en los imports.

---

## 3. Inversión de Dependencias

| Componente | Depende de ABC | Implementación concreta inyectada |
|-----------|---------------|----------------------------------|
| `AgentOrchestrator` | `Planner`, `Scheduler`, `ToolRunner`, `CapabilityGate`, `AuditLogger` | ✅ Constructor |
| `AgentScheduler` | `TaskQueue` | ✅ `_PriorityQueue` inyectable |

**Hallazgo:** Todas las dependencias de alto nivel dependen de abstracciones (ABCs), no de implementaciones concretas. La inyección de dependencias se realiza por constructor.

---

## 4. Componentes Demasiado Grandes

| Archivo | LOC | ¿Demasiado grande? |
|---------|-----|---------------------|
| `base.py` | ~230 | 10 ABCs, cada uno con 3-5 métodos abstractos. Tamaño adecuado. |
| `models.py` | ~200 | 15 dataclasses + 2 enums + 5 ID funcs. Controlado. |
| `gate.py` | ~230 | CapabilityGate + DenialCode + PermissionDecision. En el límite. |
| `scheduler.py` | ~220 | Scheduler + PriorityQueue. En el límite. |
| `runner.py` | ~245 | ToolRunner + excepciones. En el límite. |
| `planner.py` | ~145 | RuleBasedPlanner. Adecuado. |
| `agent.py` | ~149 | AgentOrchestrator. Adecuado. |

**Hallazgo:** `gate.py`, `scheduler.py` y `runner.py` están cerca del límite (250 LOC). Si crecen más allá de 300 LOC, considerar dividir.

---

## 5. APIs Públicas Innecesarias

| Símbolo | Categoría | Justificación |
|---------|-----------|---------------|
| `Agent` (ABC) | ESTABLE | Necesario para inyección |
| `AgentOrchestrator` | ESTABLE | Implementación principal |
| `AgentStateMachine` | INTERNA | Solo usado internamente |
| `PlanStep` | INTERNA | Solo usado internamente |
| `ToolAdapter` | ESTABLE | Necesario para extensiones |
| `PermissionDecision` | ADVANCED | Extensiones |
| `DenialCode` | ESTABLE | Necesario para auditoría |

**Hallazgo:** Las 42 exportaciones están clasificadas y justificadas. No se identifican símbolos innecesarios.

---

## 6. Duplicación

| Código duplicado | Ubicación | Mitigación |
|-----------------|-----------|------------|
| Lógica de creación de `FactRef`/`MemoryEntry` | No duplicada | Solo en F26 |
| Lógica de transiciones de estado | `state.py` | Una sola implementación |
| Lógica de verificación de permisos | `gate.py` | Una sola implementación |

**Hallazgo:** Sin duplicación significativa.

---

## 7. Deuda Técnica

| ID | Deuda | Prioridad |
|----|-------|-----------|
| TD01 | `gate.py`: `_evaluate` método largo (~60 LOC) con múltiples condiciones | Baja |
| TD02 | `runner.py`: `_execute_single` con lógica de timeout en thread | Media |
| TD03 | `scheduler.py`: `_run_execution` simulada (no ejecuta agentes reales) | Baja |
| TD04 | `planner.py`: `_generate_remaining` duplica lógica de `plan` | Baja |

---

## 8. Riesgos de Regresiones Futuras

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|-----------|
| Cambios en `base.py` (ABCs) afectan a todas las implementaciones | Alta | Alto | Tests de interfaz en B2 |
| Adición de nuevos estados a `AgentState` requiere actualizar `_VALID_TRANSITIONS` | Media | Medio | Test property-based en B8 |
| Sustitución de `_PriorityQueue` por cola distribuida | Baja | Medio | Abstracción `TaskQueue` ya existe |

---

## Resumen

| Categoría | Hallazgos |
|-----------|-----------|
| Violaciones SRP | 0 |
| Dependencias ocultas | 0 |
| Inversión de dependencias | ✅ Correcta |
| Componentes grandes | 3 en límite (gate, scheduler, runner) |
| APIs innecesarias | 0 |
| Duplicación | 0 significativa |
| Deuda técnica | 4 (baja/media) |
| Riesgos de regresión | 3 (controlados) |
