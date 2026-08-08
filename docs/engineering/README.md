# Engineering — Metodología Universal de Ingeniería

**Versión**: 1.0 (con ENGINEERING_PROCESS.md)
**Estado**: Implementación Plan 0 (TASK-20260808-016)
**Fuentes**: PLAN_0 (referencia maestra `docs/architecture/PLAN_0.md`), Plan 0 revisado (`docs/architecture/PLAN_0_REVISADO.md`)

## Qué es

Metodología universal para agentes de programación (OpenCode Web, OpenCode Terminal y futuros). La regla central:

> **Un plan nunca se ejecuta sin análisis previo.** El agente analiza contra la realidad del código, detecta omisiones/riesgos/contradicciones, propone mejoras, entrega veredicto (GO / GO CON CAMBIOS / NO-GO) y solo después, con aprobación, ejecuta.

## Documentos

| Archivo | Contenido |
|---------|-----------|
| [ENGINEERING_PROCESS.md](ENGINEERING_PROCESS.md) | El ciclo completo: obligaciones, clasificación, ejecución, revisión, roles, cierre (v1.0) |
| [PLAN_TEMPLATE.md](PLAN_TEMPLATE.md) | Cómo preparar un plan (las 11 preguntas obligatorias) |
| [PLAN_REVIEW_TEMPLATE.md](PLAN_REVIEW_TEMPLATE.md) | Cómo debe analizarlo el agente (ANÁLISIS DEL PLAN + veredicto + 9 preguntas) |

## Fuentes (referenciadas, no duplicadas)

- **UDO** (mecanismo): `scripts/pro/ura-udo` + `docs/udo/README.md` — reservas, estados, gate F2.2, AUTO-REVISIÓN, trazabilidad
- **Directiva permanente de clasificación**: `docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`
- **Reglas específicas de URA**: `AGENTS.md` (raíz del repo)
- **Precedentes GO/NO-GO**: `docs/udo/AUDITORIA-F3-2026-08-08.md`, `docs/architecture/PLAN_0_AUDITORIA.md`

## Instalación

La metodología se entrega a todo agente OpenCode mediante:
1. `AGENTS.md` del proyecto → sección "Metodología universal" (puntero)
2. `~/.config/opencode/AGENTS.md` (global de usuario) → copia de instalación de `deploy/engineering/AGENTS.md.global`
3. Verificación: `scripts/pro/ura-engineering-check` (versión + checksum + sincronización)

## Mantenimiento

- La fuente de verdad es este directorio (git).
- Modificaciones importantes → bump de versión en la cabecera de ENGINEERING_PROCESS.md + entrada en su changelog + commit.
- Tras cada bump, reinstalar la copia global (`deploy/engineering/AGENTS.md.global` → `~/.config/opencode/AGENTS.md`) y verificar con `ura-engineering-check`.
