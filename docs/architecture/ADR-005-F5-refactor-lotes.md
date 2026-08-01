# ADR-005-F5 — Plantilla ADR por lote de refactorización (Fase 5)

**Estado:** Aprobado (2026-08-01) · **Sprint:** 5b · **Referencia:** FASE5_PROPOSAL.md (C2/C3)

## Contexto

ADR-007 exige justificación, migración/rollback y degradación para cambios en `core/`. La Fase 5 refactoriza ~94 funciones >60 líneas y 13 con CC≥20. Crear un ADR individual por función produciría ~30 documentos repetitivos; un único ADR por lote homogéneo (C2) mantiene trazabilidad con coste documental razonable. Regla C3: un commit = una función refactorizada + su entrada en el ADR del lote.

## Plantilla de lote

Cada lote (A: CC≥20, B: LOC>60 con red F4, C: mecánico) crea `docs/architecture/ADR-005-F5-<lote>.md`:

```markdown
# ADR-005-F5-<lote> — Refactor <descripción lote>

**Estado:** En ejecución · **Sprint:** 5b · **Funciones:** <n>

## Justificación (ADR-007)
- <por qué no es alcanzable vía Protocol/EventBus/adaptador externo>

## Migración y rollback
- Commits atómicos (uno por función, reversibles individualmente)
- Rollback: git revert del commit de la función

## Degradación
- Sin cambio de comportamiento observable; oráculo = tests existentes
- Semantic freezing: firmas públicas intactas

## Funciones
| Commit | Función | Técnica | CC/LOC antes→después | Validación |
|--------|---------|---------|----------------------|------------|
| <hash> | <firma> | Extract Method / Early return | 28→<15 | pytest tests/unit -q |

## Registro
| Fecha | Acción |
|-------|--------|
| 2026-08-01 | Apertura lote |
```

## Criterios de inclusión

- Una función por commit; mensaje ≤100 chars: `refactor(core): descomponer <fn> en <archivo> — CC n→m, LOC x→y`
- Prohibido mezclar refactor con bugfix (los bugs M7 van en commit aparte con ADR propio)
- Funciones sin red de tests: test de seguridad previo en commit separado (C1)
