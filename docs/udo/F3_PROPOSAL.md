# F3 — Revisión Formal (Anexo A, Fase 3)

**Estado:** ✅ En implementación (TASK-20260808-009)
**Fecha:** 2026-08-08

## Objetivo

Terminal pasa a tener un **procedimiento formal de revisión** sobre el trabajo de
Web: ciclo de estados con rework, y checklist de comprobaciones automáticas antes
de emitir veredicto.

## Ciclo de estados

```text
IN_PROGRESS → REVIEW → CHANGES_REQUESTED → IN_PROGRESS → REVIEW → APPROVED → DONE
```

## Máquina de transiciones (implementada en `update`)

| Desde | Permitidas |
|---|---|
| PLANNED | IN_PROGRESS, BLOCKED, CANCELLED |
| IN_PROGRESS | REVIEW, BLOCKED, CONFLICT, CANCELLED |
| REVIEW | APPROVED, CHANGES_REQUESTED, BLOCKED, CANCELLED |
| CHANGES_REQUESTED | IN_PROGRESS, CANCELLED |
| APPROVED | DONE, CANCELLED |
| BLOCKED | IN_PROGRESS, CANCELLED |
| CONFLICT | IN_PROGRESS, BLOCKED, CANCELLED |
| DONE | CANCELLED |

Saltos excepcionales: `--force` (uso consciente, queda en historial).

## Procedimiento de revisión

```bash
ura-udo review TASK-ID                      # checklist sin veredicto
ura-udo review TASK-ID --approve "nota"     # → APPROVED
ura-udo review TASK-ID --changes "razón"    # → CHANGES_REQUESTED (rework)
```

Checklist automático (8 comprobaciones):

1. **ESTADO** — debe estar en REVIEW/CHANGES_REQUESTED
2. **COMMIT** — existe commit con `[TASK-ID]`
3. **DIFF** — rango `commit_base..HEAD`, nº de archivos
4. **ARCHIVOS** — modificados sin declarar vs reserva (invasión)
5. **REQUISITOS** — campos `objetivo:` / `resultado:` cumplimentados
6. **TESTS** — evidencia de validación en el expediente
7. **DOCUMENTACIÓN** — pendiente de veredicto / veredicto previo
8. **REGRESIONES** — git limpio (sin cambios sin commitear fuera del rango)

El veredicto se registra en `revision:` y en historial, con revisor
(`URA_REVISOR`, default TERM) y fecha. La reserva sigue activa en
CHANGES_REQUESTED (quien corrige es el ejecutor; el revisor no pisa la zona).

## No implementado (fuera de F3)

- Delegación auxiliar con tipos (MAINTENANCE/CLEANUP/...) → F4
- Automatización de conflictos/cambios no declarados/trazabilidad → F5
