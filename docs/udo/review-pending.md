# Revisión pendiente (review-pending) — tareas AUTO-REVISADAS sin revisión independiente

**Política (Engineering Process v1.1 §9, PLAN 1 B1)**: cuando una tarea se cierra DONE con AUTO-REVISIÓN (revisor idle o inexistente), se registra aquí. Al cerrar una fase, el lote se revisa en bloque por el otro agente o por Ramón. Una fase no se cierra con el lote sin revisar o sin aceptación explícita.

**Formato de registro**:

```
| TASK | Descripción | Fecha cierre | Ejecutor | Estado revisión | Revisor | Fecha revisión | Veredicto |
|------|-------------|--------------|----------|-----------------|---------|----------------|-----------|
```

| TASK | Descripción | Fecha cierre | Ejecutor | Estado revisión | Revisor | Fecha revisión | Veredicto |
|------|-------------|--------------|----------|-----------------|---------|----------------|-----------|
| TASK-20260808-006 | Auditoría F2 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-012 | Endurecimiento F2 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-013 | F2.2 garantías de revisión (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-015 | Auditoría Plan 0 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-016 | Implementación Plan 0 (cierre AUTO-REVISIÓN) | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260808-019 | Implementación PLAN 1 | 2026-08-08 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260809-001 | Implementación F4+F5 (prueba real) | 2026-08-09 | TERM | ✅ REVISADA | Ramón | 2026-08-09 | APROBADA |
| TASK-20260810-003 | Prueba de círculo UDO (veredicto Web->Mac->ASUS) | 2026-08-10 | TERM | ⏳ PENDIENTE | — | — | — |
| TASK-20260810-004 | Fix bucle auto-merge Mac<->ASUS + ura-udo portable bash3.2 | 2026-08-10 | TERM | ⏳ PENDIENTE | — | — | — |

**Lote actual**: 2 tareas pendientes de revisión independiente (cierre AUTO-REVISIÓN 2026-08-10, TERM). La revisión de este lote forma parte del cierre del PLAN 1 (B1) y del F5.

---

*Este archivo es un registro de proceso (Git), no una BD: cada fila enlaza al expediente UDO correspondiente en `docs/udo/tasks/`.*
