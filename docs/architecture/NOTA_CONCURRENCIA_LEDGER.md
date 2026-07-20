# Nota Arquitectónica: Concurrencia en el ExecutionLedger

**Fecha:** 2026-07-20  
**Hallazgo D3:** Sin locks en componentes de autonomía  
**Estado:** Riesgo latente — no afecta hoy, documentado para futuro

---

## El problema

El ExecutionLedger, GoalManager, PolicyEngine y otros componentes de
autonomía no tienen protección de concurrencia (locks, semáforos, OCC).

Actualmente el sistema es estrictamente secuencial: un objetivo tras otro,
un agente tras otro, sin paralelismo. Por tanto, no hay race conditions.

## Criterio de activación

> Si cualquier componente empieza a escribir simultáneamente en el
> ExecutionLedger, la implementación deberá incorporar sincronización
> (threading.Lock, sqlite3 con WAL, o equivalente) **antes** de habilitar
> esa funcionalidad.

## Componentes afectados

| Componente | Riesgo si se paraleliza |
|-----------|------------------------|
| `ExecutionLedger.save()` | Dos escrituras simultáneas → archivo corrupto |
| `GoalManager._goals` | Dos threads modificando el dict → pérdida de estado |
| `PolicyEngine._applied` | Lista compartida sin protección |

## Recomendación

Si en el futuro se añade:
- Ejecución paralela de objetivos
- Agentes concurrentes
- Escritura simultánea desde múltiples fuentes

Entonces implementar antes:
- `threading.Lock` en `ExecutionLedger.save()`
- `sqlite3` con WAL mode para el ledger (en lugar de JSON files)
- O usar la memoria semántica (SQLite, WAL mode) como backend de escritura
