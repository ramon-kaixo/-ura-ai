# ADR-004: Archive asíncrono (fire-and-forget)

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
El archive (git bundle + manifest + registro en op_archives) puede ser lento para repositorios grandes. No debe bloquear el compile ni la respuesta al usuario.

## Decisión
- El archive se encola en `op_jobs` post-compile (`enqueue_archive_job()`)
- Se procesa en un ciclo separado (`process_archive_jobs()`)
- Si el archive falla, el compile NO se revierte
- Consumidor: systemd timer ejecutando `ke job-process`

## Consecuencias
- Positivas: compile no bloqueado por archive. Falla de archive no afecta al grafo.
- Negativas: Ventana entre compile y archive donde no hay backup del source.
