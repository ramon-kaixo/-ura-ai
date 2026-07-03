# ADR-005: SQLite WAL mode

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
El Knowledge Engine tiene múltiples lectores (Reader, CLI, API) y un escritor (compile) accediendo simultáneamente a SQLite. El modo journal por defecto (DELETE) bloquea lectores durante escrituras.

## Decisión
- WAL (Write-Ahead Logging) activado en todas las conexiones vía `connection.py`
- `busy_timeout = 5000ms` para escritores concurrentes
- `synchronous = NORMAL` (balance entre durabilidad y rendimiento)
- `journal_size_limit = 64MB` (WAL no crece indefinido)
- Writers usan `BEGIN IMMEDIATE` para evitar deadlock entre lectores/escritores

## Consecuencias
- Positivas: Lectores nunca bloquean escritores. Escritura concurrente con reintento.
- Negativas: WAL crece hasta checkpoint. Punto único de configuración (connection.py).
