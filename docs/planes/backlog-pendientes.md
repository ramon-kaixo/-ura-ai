# Backlog consolidado de pendientes — URA

Generado el 2026-09-02. Fuentes: docs/audit/baseline, coordination.json, hallazgos-fondo.

| ID | Descripción | Prioridad | Fuente | Estado | Responsable |
|----|-------------|-----------|--------|--------|-------------|
| B001 | Errores mypy attr-defined/union-attr producción (quedan 11) | P0 | mypy | EN_PROGRESO | TERM/WEB |
| B002 | Errores mypy P1 producción (~108) | P1 | C1_mypy_classification | PENDIENTE | TERM |
| B003 | Errores mypy en tests (~242) | P2 | C1_mypy_classification | PENDIENTE | WEB |
| B004 | Deuda menor mypy (~21) | P3 | C1_mypy_classification | PENDIENTE | TERM |
| B005 | Deuda ruff: S110, PTH, PLR0917 | P3 | ruff | PENDIENTE | TERM |
| B006 | Servicios systemd legacy (14) | P2 | B3 | RESUELTO | TERM |
| B007 | Servicios dudosos (llama-vision, snc, swarm-discovery) | P3 | B3 | RESUELTO | RAMÓN |
| B008 | Hook semgrep roto por falta de semgrep en venv | P2 | B4 | RESUELTO | TERM |
| B009 | /tmp con archivos temporales OpenCode creciendo | P0 | disco | RESUELTO | RAMÓN |
| B010 | Consolidación de modelos LLM (duplicados) | P1 | auditoría disco | RESUELTO | RAMÓN |
| B011 | Documentación obsoleta (OpenClaw retirado, duplicados EN/ES) | P2 | F5 | EN_PROGRESO | WEB |
| B012 | Integrar auto-dispatcher con despertador (TASK-009) | P2 | TASK-009 | RESUELTO | TERM |
| B013 | Plan F6-F10 producción robusta | P2 | TASK-011 | PENDIENTE (desbloqueada) | RAMÓN |
| B014 | Cambios ajenos sin commitear | P1 | git status | RESUELTO | RAMÓN |
| B015 | TASK-025 clasificación mypy en revisión | P2 | TASK-025 | REVISADO (prod 0 errores, tests documentados) | WEB |
| B016 | TASK-027 correcciones mypy alto riesgo en revisión | P1 | TASK-027 | REVISADO (prod 0 errores, P0 corregidos en TASK-027) | WEB |
| B017 | Carpeta descarte_temporal (respaldos no versionados/código obsoleto, auto-borrado 90 días, timer systemd diario) | P2 | TASK-20260828-003 | RESUELTO | TERM/WEB |

## Notas
- Los pendientes P0 activos son pocos y controlados.
- La consolidación de modelos LLM se hará en bloque aparte.
- Este backlog se actualizó 2026-09-02: B006, B007, B008, B010, B012, B017 RESUELTOS.
- F5 (TASK-013) APROBADO -> B013 (F6-F10) DESBLOQUEADA.
- F5 (TASK-013) en progreso -> desbloquea F6-F10 (B013).
- Este backlog se actualizará al cierre de cada TASK.
