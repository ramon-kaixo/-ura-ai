# ADR-002: flock(2) para exclusión mutua del compile

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
Múltiples fuentes (CLI, watcher, scheduler, API, agente) pueden solicitar compilaciones simultáneas. Sin exclusión mutua, writes concurrentes a SQLite causan SQLITE_BUSY.

## Decisión
- Lock a nivel de proceso: `fcntl.flock(LOCK_EX | LOCK_NB)` sobre un archivo
- No usar LOCK_NB → fallo inmediato si otro compile está en ejecución
- El lock se libera automáticamente si el proceso muere (el SO cierra el fd)

## Consecuencias
- Positivas: Sin riesgo de deadlock. Sin necesidad de cleanup. Funciona entre procesos.
- Negativas: Un compile largo (ej. 1000 docs) bloquea otros compiles. No hay cola de compilación.
