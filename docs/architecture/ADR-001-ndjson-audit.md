# ADR-001: NDJSON para auditoría del read path

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
El Knowledge Engine necesita auditoría para todas las operaciones de lectura (search) y escritura (compile, archive). El read path debe ser lock-free para no degradar la latencia de búsqueda.

## Decisión
- Read path: NDJSON append-only (sin lock, sin SQLite)
- Write path: Ingesta batch NDJSON → SQLite (op_audit)
- Backend desacoplado vía `AuditBackend(Protocol)`

## Consecuencias
- Positivas: Read path completamente lock-free. Sin contención SQLite en búsquedas.
- Negativas: Dos formatos de almacenamiento (NDJSON + SQLite). Necesidad de ingesta batch periódica.
