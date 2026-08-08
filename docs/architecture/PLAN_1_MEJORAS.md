<!-- PLAN_TEMPLATE v1.0 — Engineering Process -->

# PLAN 1 — Corrección post-implantación Plan 0: fallos y mejoras

- **Estado**: PROPUESTO (pendiente de análisis y aprobación de Ramón)
- **Fecha**: 2026-08-08
- **Versión**: 1.0
- **Autor / Solicitante**: Ramón (vía TASK-20260808-018, preparado por TERM)
- **Base**: `docs/architecture/PLAN_0_POSTIMPLANTACION.md` (9 hallazgos verificados: B1-B2, N1-N3, M1-M2, D1-D2)

---

## 1. ¿QUÉ QUIERO CONSEGUIR?

Que la metodología universal de ingeniería (Plan 0) sea **eficaz de verdad**, no solo esté instalada. Concretamente, resolver los 9 hallazgos de la revisión post-implantación:

| Id | Hallazgo | Resultado deseado |
|----|----------|-------------------|
| **B1** | El gate UDO no verifica el análisis previo | Ninguna tarea cierra DONE sin análisis registrado |
| **B2** | No existe comprobación del entorno antes de trabajar | `ura-engineering-check --env` detecta entorno degradado ANTES de empezar |
| **D1** | La validación no queda registrada estructuralmente | El expediente registra qué pruebas pasaron |
| **D2** | La Web en ejecución no ha cargado la metodología | El reinicio tras instalar reglas queda documentado y verificado |
| **N1** | Sin política de revisor independiente operativa | Revisión diferida por lotes cuando el revisor está idle; nunca se finge |
| **N2** | La prueba de eficacia es de presencia, no de conducta | 4 planes de ejemplo reales demuestran que el agente detecta defectos |
| **N3** | Sin postmortem retrospectivo | `POSTMORTEMS.md` con ~20 incidentes de 4 meses, causa raíz y regla preventiva |
| **M1** | Divergencia entre máquinas no cubierta | Mac documentado como instalación equivalente; check avisa |
| **M2** | Riesgo de burocracia (teatro de proceso) | Proporcionalidad: plan trivial → análisis breve |

## 2. ¿POR QUÉ?

- La regla central del Plan 0 ("un plan nunca se ejecuta sin análisis previo") **depende de la buena voluntad del LLM**: el gate UDO no la refuerza (verificado: `_gate_revision` ura-udo:127-160 solo comprueba commits/pinning/árbol; `revision:` vacío en 15/16 expedientes).
- El entorno degradado se descubre trabajando, no antes (hoy: rootfs `ro` bloqueó la instalación; patrón recurrente de 4 meses).
- La revisión independiente no ocurre de facto (0 commits `[WEB]` en el verano); los errores más caros (2356 lint, config duplicada, secretos) los detectó el humano o auditorías puntuales.
- §46 de la metodología exige evidencia antes de mejorar el proceso — sin postmortem no hay base.

## 3. ¿QUÉ CONTEXTO EXISTE?

- Plan 0 implementado y cerrado: `docs/engineering/` (4 archivos, v1.0), AGENTS.md puntero, `~/.config/opencode/AGENTS.md` instalado y verificado por checksum, `ura-engineering-check` OK, tag `v0.31.0-plan0`, closeout. ✅
- UDO operativo: `ura-udo` (7 estados, gate F2.2, AUTO-REVISIÓN, reservas, 30 asserts en `tests/udo/test_udo.sh`), tag `v0.30.0-f2`. ✅
- Revisión post-implantación: `docs/architecture/PLAN_0_POSTIMPLANTACION.md` (TASK-017, 9 hallazgos verificados). ✅
- Entorno: rootfs `/` ro de forma recurrente (F14-F01); Web idle de facto (0 commits [WEB]); Web arrancada 00:29 sin la metodología cargada (config no hot-reload); Mac sin copia de la metodología.
- Restricciones conocidas: AGENTS.md "Regla Transversal" (cerrar fases con validación, docs, baseline, tag, acta); ADR-007 (núcleo congelado — este plan no toca core/); Regla Global de No Regresión (baseline 5251 tests).

## 4. ¿QUÉ TIENE QUE HACER? (Alcance — 2 tramos)

### TRAMO A — Parche Plan 0 v1.0.1 (defectos de la implantación: B1, B2, D1, D2 + M1)

| # | Cambio | Archivo(s) | Verificación |
|---|--------|------------|--------------|
| A1 | Campo `analisis:` en expediente UDO + `update --analisis "..."` + gate DONE exige campo no vacío (B1) | `scripts/pro/ura-udo`, `docs/udo/templates/task_template.md`, `tests/udo/test_udo.sh` | nuevos asserts; suite 30/30 sin regresión |
| A2 | Campo `validacion:` + gate DONE exige no vacío (D1) | ídem A1 | ídem |
| A3 | Subcomando `--env` en `ura-engineering-check` (B2): rootfs rw/ro, servicios críticos (opencode, model-router, ollama, ura-api), secretos presentes, disco, git limpio | `scripts/pro/ura-engineering-check` | `--env` OK en ASUS; FAIL simulado |
| A4 | Documentar reinicio de opencode.service tras instalar/actualizar reglas + verificación (D2) | `docs/engineering/ENGINEERING_PROCESS.md` §11 + `docs/architecture/PLAN_0_CLOSEOUT.md` | texto presente |
| A5 | Documentar instalación equivalente en Mac + aviso del check (M1) | `docs/engineering/ENGINEERING_PROCESS.md` §13 | texto presente |

**Bump metodología**: ENGINEERING_PROCESS → v1.0.1 con changelog (cambios de proceso: análisis/validación obligatorios).

### TRAMO B — Mejoras (N1, N2, N3, M2)

| # | Cambio | Archivo(s) | Verificación |
|---|--------|------------|--------------|
| B1 | Política de revisión independiente con degradación: (a) cierre AUTO-REVISADO → registro en `docs/udo/review-pending.md`; (b) al cerrar fase, revisión cruzada por lotes; (c) la fase no cierra si el lote queda sin revisar o sin aceptación explícita de Ramón | `docs/udo/README.md`, `docs/engineering/ENGINEERING_PROCESS.md` §9, `docs/udo/review-pending.md` (nuevo) | doc + 1 caso de prueba manual |
| B2 | Prueba de eficacia conductual: 4 planes de ejemplo (correcto / incompleto / contradictorio / fase futura) + procedimiento de evaluación (agente completa ANÁLISIS DEL PLAN; criterio: ≥3/4 defectos detectados) | `tests/engineering/planes/*.md` (4), `tests/engineering/README.md` | evaluación manual por Ramón o revisión cruzada |
| B3 | Postmortem retrospectivo: `docs/engineering/POSTMORTEMS.md` con ~20 incidentes de 4 meses (fecha, síntoma, causa raíz, ¿fallo de proceso?, regla preventiva, estado) | `docs/engineering/POSTMORTEMS.md` (nuevo) | tabla con ≥15 incidentes completos |
| B4 | Proporcionalidad en revisión: PLAN_REVIEW_TEMPLATE indica "plan trivial → análisis de 5 líneas; plan complejo → análisis completo"; métrica de coste en closeout (tiempo análisis vs ejecución) | `docs/engineering/PLAN_REVIEW_TEMPLATE.md`, `docs/architecture/PLAN_0_CLOSEOUT.md` | texto presente |

**Bump metodología**: ENGINEERING_PROCESS → v1.1 con changelog (política de revisión, proporcionalidad, postmortem).

## 5. ¿QUÉ ES MÍNIMO? (Mínimos obligatorios)

1. **A1+A2**: gate DONE rechaza sin `analisis:` y `validacion:` no vacíos (suite 30/30 + nuevos asserts).
2. **A3**: `ura-engineering-check --env` funciona y da OK en ASUS.
3. **A4+A5**: reinicio de Web documentado; Mac documentado.
4. **B1**: política de revisión documentada + `review-pending.md` operativo (una tarea AUTO-REVISADA registrada).
5. **B2**: 4 planes de ejemplo creados; evaluación realizada con ≥3/4 defectos detectados.
6. **B3**: POSTMORTEMS.md con ≥15 incidentes completos.
7. **B4**: proporcionalidad en template.
8. Bumps de versión (v1.0.1 y v1.1) + changelog.
9. 0 regresiones: `make validate` 5251 passed; suite UDO 30/30.

## 6. ¿QUÉ ES CRÍTICO? (Puntos críticos / Invariantes)

- **Compatibilidad**: las tareas UDO ya cerradas (001-016) no se tocan; el gate nuevo solo exige `analisis:`/`validacion:` a tareas nuevas que lleguen a DONE tras el parche.
- **Trazabilidad**: análisis y validación quedan en el expediente (Git), nunca solo en la conversación.
- **No regresión**: 0 regresiones funcionales vs tag `v0.31.0-plan0`.
- **Reversibilidad**: quitar los 2 campos + revertir `--env` + borrar review-pending.md deja todo como antes (sin BD, sin servicios).
- **Anti-sobreingeniería**: todo son campos de texto, subcomandos y documentos — NADA de infraestructura nueva.
- **Honestidad**: la prueba B2 es conducta LLM, se marca como tal (evaluación humana); AUTO-REVISIÓN sigue siendo automática y explícita.
- **Contratos**: no se toca core/, motor/ ni la API de UDO pública; `--force` sigue siendo la excepción auditada.

## 7. ¿CÓMO DEBE COMPORTARSE? (Comportamiento esperado)

- Al cerrar DONE de una tarea nueva sin `analisis:` → el gate lo rechaza con mensaje claro ("ERROR: DONE requiere analisis — usa update --analisis").
- Antes de empezar cualquier sesión de trabajo: `ura-engineering-check --env` informa del estado del entorno (OK/WARN/FAIL).
- Al cerrar una fase con tareas AUTO-REVISADAS → el cierre documenta el lote de `review-pending.md` (revisado o aceptado por Ramón).
- Un agente que recibe un plan de ejemplo defectuoso → produce ANÁLISIS DEL PLAN que detecta el defecto (≥3/4).
- El proceso no entorpece: plan trivial → análisis breve; plan complejo → análisis completo.

## 8. ¿QUÉ NO DEBE HACER? (NO HACER)

- NO crear BD, servicios, APIs, paneles, colas, dispatchers, sistemas de carga propios.
- NO tocar core/, motor/, adapters/ ni el motor de URA.
- NO implementar F4/F5 (funcionalidad de negocio del roadmap URA).
- NO migrar secretos del `.bashrc` (tarea de seguridad aparte, requiere sudo y rotación).
- NO instalar timers de mutmut.
- NO cambiar la semántica de los 7 estados UDO ni del gate F2.2 existente (solo añadir 2 campos).
- NO exigir análisis retroactivo a tareas ya cerradas.
- NO tocar `~/.config/opencode/opencode.json` (config técnica; la limpieza de `mcp.openclaw` queda como pendiente sudo aparte).

## 9. ¿QUÉ ESTÁ FUERA DE ALCANCE?

- Migración de secretos `.bashrc` → `/etc/ura/secrets.env` + rotación (PENDIENTE, requiere sudo).
- Limpieza de restos del sistema: `mcp.openclaw`, `ReadWritePaths=.openclaw`, residuos `~/.opencode/` (PENDIENTE, requiere sudo/rootfs rw).
- F4/F5 del roadmap de URA.
- Cualquier mejora del motor de URA.
- Automatización total de la evaluación conductual (B2 es evaluación humana por diseño — ser honestos).

## 10. ¿CÓMO SE VALIDARÁ?

- **A1/A2**: asserts nuevos en `tests/udo/test_udo.sh` (gate rechaza sin analisis/validacion; acepta con ambos) + suite completa 30/30.
- **A3**: `ura-engineering-check --env` → OK en ASUS; prueba de FAIL con un servicio parado simulado.
- **B2**: evaluación real: TERM (o WEB) completa ANÁLISIS sobre los 4 planes; Ramón valida el resultado (≥3/4).
- **B3**: revisión de la tabla (≥15 incidentes con los 5 campos).
- **Global**: `make validate` 5251 passed 0 regresiones; ruff sin errores nuevos (los cambios son bash/markdown — sin impacto Python); suite UDO 30/30; árbol limpio; expedientes con análisis/validación registrados.

## 11. ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO? (Criterios de cierre)

1. A1-A5, B1-B4 implementados y verificados (tablas §4 completas).
2. Suite UDO con nuevos asserts (≥34) 0 FAIL; `make validate` 5251 passed.
3. `ura-engineering-check` (reglas) OK + `--env` OK en ASUS.
4. Evaluación conductual B2 realizada con resultado documentado (≥3/4).
5. POSTMORTEMS.md con ≥15 incidentes.
6. ENGINEERING_PROCESS v1.1 (bumps 1.0.1 → 1.1 con changelog) + copia global reinstalada + checksum OK + **reinicio de opencode.service** (D2) documentado/ejecutado.
7. Closeout `docs/architecture/PLAN_1_CLOSEOUT.md` + tag (propuesto: `v0.31.1-plan1`) + árbol limpio.
8. Cierre con revisión: AUTO-REVISIÓN si no hay revisor independiente, o lote review-pending revisado por Ramón.

---

# ANÁLISIS DEL PLAN (por TERM, antes de ejecución)

## Qué he comprobado (verificado contra el código, no asumido)

- Gate UDO: `_gate_revision` (ura-udo:127-160) — confirmado: no comprueba análisis ni validación. ✅ hallazgo B1 real.
- Expedientes: `revision:` vacío en 15/16; solo TASK-010 lo pobló (formato F3 retirado). ✅ D1 real.
- `ura-engineering-check`: solo reglas, sin entorno. ✅ B2 real.
- Web: arrancada 00:29, AGENTS.md global instalado 18:10 — config no hot-reload. ✅ D2 real.
- Mac: AGENTS.md:12-16 flujo manual scp/rsync; sin copia de metodología. ✅ M1 real.
- Tests actuales: `test_engineering.sh` verifica cadenas en archivos, no conducta. ✅ N2 real.
- Baseline: make validate 5251 (closeout previo); suite UDO 30/30.

## Qué coincide

- Los 9 hallazgos de POSTIMPLANTACION son reales y este plan los cubre todos.
- Tramo A es acotado y sin infraestructura; Tramo B es documentación + archivos de proceso.
- El reparto parche/mejoras coincide con la revisión previa.

## Qué falta (autoanálisis — añadido aunque no lo pidió Ramón explícitamente)

| Id | Hallazgo del plan | Clase | Resolución |
|----|-------------------|-------|------------|
| X1 | La suite `test_engineering.sh` existente (13 asserts de presencia) no cubrirá la prueba conductual B2 — mantener ambas, no mezclar | NECESARIO | B2 crea `tests/engineering/planes/` separado |
| X2 | Al añadir campos al gate, `ura-udo verify` debe mostrar discrepancias si `analisis:` falta (retrocompatibilidad con tareas antiguas en REVIEW) | NECESARIO | A1: verify muestra WARNING no error para tareas pre-parche |
| X3 | El reinicio de opencode.service (D2) puede caer en F14-F01 (polkit interactivo) — documentar el comando sudo y la degradación si no se puede | NECESARIO | A4: comando `systemctl restart opencode.service` con nota de sudo |
| X4 | POSTMORTEMS debe incluir los incidentes de ESTA sesión (rootfs ro recurrente, IFS bug de sesión paralela, TASK-014 accidental) — no solo los de AGENTS.md | MEJORA | B3: incluir sesión 2026-08-08 |

## Qué riesgos existen

- **Riesgo de retocar el gate**: romper la suite 30/30 → mitigado: asserts nuevos + compatibilidad WARNING.
- **Riesgo de burocracia (M2)**: que A1 (análisis obligatorio) añada fricción a tareas triviales → mitigado: proporcionalidad B4 entra en el mismo plan.
- **Riesgo de divergencia de interpretación del análisis**: el campo `analisis:` es texto libre — el gate solo exige no vacío; la calidad la juzga el revisor humano. Honestidad: es lo máximo sin sobreingeniería.

## Qué cambiaría / qué no tocaría

- Cambiaría: nada del alcance; orden de ejecución propuesto: A1→A2→A3→A5→A4 (primero gate, luego entorno, luego docs) y B3→B1→B4→B2 (postmortem primero — es la evidencia).
- No tocaría: core/, motor/, estados UDO, gate F2.2 existente, config global de opencode, secretos.

## Propuesta de plan corregido

El plan es correcto tal cual con 2 ajustes incorporados arriba: X2 (verify con WARNING para tareas pre-parche) y X3 (comando sudo documentado para el reinicio). Nada más.

## Valoración final

Plan sólido, mínimo, sin infraestructura nueva, compatible con el historial. Los dos bloqueantes se corrigen en el Tramo A; las mejoras en el Tramo B. Riesgo bajo de regresión (bash + markdown + doc). El único punto de honestidad: la prueba conductual B2 depende de evaluación humana, se documenta como tal.

---

## VEREDICTO: GO CON CAMBIOS

(Los 2 ajustes X2, X3 deben incorporarse — ya están en el plan corregido. Valoración técnica para Ramón; la decisión de autorizar es suya.)
