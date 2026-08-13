# PLANTILLA DE PLAN — docs/udo/plans/

Rol Orquestador (OpenClaw, perfil `orquestador`): esta es la única zona de
escritura del rol. El resto del repo es read-only para él. Los planes son
propuestas — el veredicto es del humano (Plan 0). Ver
`docs/udo/OPENCLAW-ORQUESTADOR.md`.

## Plantilla mínima (PLAN-YYYYMMDD-SLUG.md)

```markdown
# PLAN-YYYYMMDD-SLUG — <Título>

- **Autor**: OpenClaw (rol orquestador) — fecha
- **Solicitante**: RAMON

## OBJETIVO
<qué resultado debe existir, para qué>

## ALCANCE
- Dentro: <>
- Fuera: <>

## FASES
| # | Fase | TASK UDO (id) | Estado | Revisor cruzado |
|---|------|--------------|--------|-----------------|
| 1 | <descripción> | TASK-YYYYMMDD-NNN | PLANEADA/EN CURSO/TERMINADA/REVISADA | WEB|TERM |

## RIESGOS
<riesgos conocidos y mitigación>

## VERIFICACIÓN
<comandos/suites que demuestran el objetivo cumplido>

## NO HACER
<lo que está explícitamente prohibido en este plan>

## ESTADO (bitácora, la actualiza el orquestador read-only? NO: la actualiza el
coordinador o el agente ejecutor en cada avance; el orquestador lee)
- YYYY-MM-DD: plan creado, enviado a revisión.
- YYYY-MM-DD: TASK creada por <agente>; avance <n>.
- YYYY-MM-DD: cierre con veredicto <revisor>.
```

## RESUMEN (RESUMEN-YYYYMMDD-SLUG.md)

Resumen de resultados para la decisión de Ramón, tras leer git + expedientes
(read-only): qué se hizo, con qué evidencia (commits, tests, CI), qué quedó
pendiente, recomendación.

## Reglas del workspace

1. Un archivo por plan (slug corto en kebab-case) + un resumen por plan cerrado.
2. El orquestador escribe SOLO aquí; los agentes ejecutores actualizan el ESTADO
   en el expediente UDO (no en el plan).
3. La bitácora ESTADO la mantienen ejecutor/revisor en el expediente; el plan
   refleja la propuesta inicial y el resumen final.
4. 1 plan activo por ronda (anti-bucle).