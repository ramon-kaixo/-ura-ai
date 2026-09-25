# ADR-030: Infraestructura Congelada en v2.3

**Estado:** Aprobado  
**Fecha:** 2026-07-20  
**Infraestructura base:** v2.3 (PipelineEngine, tuneladoras, ExecutionLedger, checkpoints)

---

## Decisión

El PipelineEngine, las dos tuneladoras, el ExecutionLedger y el sistema de
checkpoints constituyen la infraestructura base de URA. Cualquier cambio
en estos componentes requiere una justificación técnica demostrable y debe
mantener la compatibilidad con los plugins existentes.

## Alcance congelado

| Componente | Archivo | Permitido |
|------------|---------|-----------|
| PipelineEngine | `scripts/pro/tuneladora/engine.py` | ❌ Solo bug fixes |
| Configuration | `scripts/pro/tuneladora/config.py` | ❌ Solo bug fixes |
| Logger | `scripts/pro/tuneladora/logger.py` | ❌ Solo bug fixes |
| SnapshotService | `scripts/pro/tuneladora/snapshot.py` | ❌ Solo bug fixes |
| ExecutionLedger | `scripts/pro/tuneladora/ledger.py` | ✅ Extensiones permitidas (nuevos campos) |
| CheckpointManager | `scripts/pro/tuneladora/checkpoint.py` | ❌ Solo bug fixes |
| Tuneladora mantenimiento | `scripts/pro/tuneladora_mantenimiento.py` | ❌ Solo bug fixes |
| Tuneladora mejora | `scripts/pro/tuneladora_mejora.py` | ❌ Solo bug fixes |
| Pipeline refactor | `scripts/pro/pipeline_refactor.py` | ❌ Solo bug fixes |
| WorkerManager | `scripts/pro/worker_manager.py` | ❌ Solo bug fixes |
| plugin_registry | `scripts/pro/plugin_registry.py` | ✅ Nuevos campos en PLUGIN |

## Próximo hito: v3.0 — Autonomía

El desarrollo se centrará en capacidades funcionales implementadas como
plugins o componentes separados que usan la infraestructura existente:

- Planificador de objetivos
- Ejecución de planes multi-paso
- Gestión de prioridades
- Memoria de trabajo
- Recuperación ante fallos a nivel de tarea
- Aprendizaje a partir de resultados

## ExecutionLedger como base de aprendizaje

El ExecutionLedger debe evolucionar para responder:

- ¿Qué decisiones tomó URA y por qué?
- ¿Qué hipótesis evaluó?
- ¿Qué herramientas utilizó?
- ¿Qué cambios produjo?
- ¿Qué resultados obtuvo?
- ¿Qué aprendió de esa ejecución?

No se modifica la estructura actual. Las extensiones se añaden como
nuevos campos opcionales, manteniendo compatibilidad con registros existentes.

## Historial de versiones de infraestructura

| Versión | Cambio |
|---------|--------|
| v2.0-tuneladora | Motor compartido + 2 tuneladoras |
| v2.0.1 | Hardening |
| v2.1 | Puerta de decisión + restricción refactor |
| v2.2 | 6 safeguards |
| **v2.3** | **Pipeline resiliente (checkpoint, ledger, presupuesto)** — CONGELADO |
