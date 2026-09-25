# ADR-006: systemd timer como consumidor de op_jobs

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
`op_jobs` acumula trabajos de compilación y archive. Necesita un proceso que los consuma. Las opciones son: daemon persistente, hilo interno del API, o timer externo.

## Decisión
- Consumidor: systemd timer ejecutando `ke job-process` cada 5 minutos
- No hay daemon ni thread interno
- `compile_worker()` lee `op_jobs` con `job_type='compile'`, los ejecuta vía `compile_source()`
- `process_archive_jobs()` maneja `job_type='archive_source'`

## Consecuencias
- Positivas: Sin proceso residente. Recuperación automática tras crash (systemd reinicia el timer). Simplicidad operativa.
- Negativas: Latencia de hasta 5 minutos entre encolado y ejecución. No apto para trabajos síncronos.
