# Prueba conductual de la metodología (PLAN 1 B2 / §44 casos 1-6)

## Qué es

Prueba de **conducta LLM real** (no de presencia): un agente recibe planes de ejemplo defectuosos y debe detectar los defectos aplicando la metodología (ANÁLISIS DEL PLAN + veredicto). Complementa a `test_engineering.sh` (que solo verifica que los documentos existen y contienen las reglas).

## Limitación honesta

NO es automatizable: depende del LLM. La evaluación la hace un humano (Ramón) o una revisión cruzada TERM/WEB. Un resultado se considera éxito si el agente detecta el defecto del plan y lo clasifica correctamente.

## Los 4 planes

| Plan | Defecto esperado | Qué debe detectar el agente |
|------|------------------|------------------------------|
| `plan_correcto.md` | Ninguno | Verificable → veredicto GO |
| `plan_incompleto.md` | Faltan MÍNIMOS, VALIDACIÓN, NO HACER, criterio de cierre verificable | El plan "se cierra porque los campos existen" (anti-§48); declarar incompleto → GO CON CAMBIOS |
| `plan_contradictorio.md` | Contradice ADR-007 (núcleo congelado, sin ADR) y la realidad (core/config.py ya no existe) | Detectar la contradicción plan vs decisión documentada → NO-GO |
| `plan_fase_futura.md` | Trabajo de F4 (panel + BD + servidor) durante F3; además viola anti-sobreingeniería (§20/§47) | Señalar trabajo prematuro (obligación 9) sin implementarlo → NO-GO |

## Procedimiento

1. Entregar a un agente (TERM o WEB) el plan y pedir: "Aplica la metodología de ingeniería (PLAN_REVIEW_TEMPLATE) a este plan. Devuelve ANÁLISIS + veredicto. NO implementes."
2. Evaluar: ¿detectó el defecto? ¿clasificó correctamente (obligatorio/mejora/fuera de alcance)? ¿veredicto correcto?
3. Registrar el resultado aquí (tabla abajo).

## Criterio de éxito

≥3 de 4 defectos detectados en primera pasada (75%). Cada fallo → evidencia para §46 (mejora del proceso).

## Registro de evaluaciones

| Fecha | Agente | Plan | Defecto detectado (S/N) | Veredicto emitido | Veredicto esperado | Evaluador |
|-------|--------|------|-------------------------|-------------------|--------------------|-----------|
| 2026-08-08 | TERM | correcto | N (no hay defecto — verificado: plan completo 11 secciones, mínimo/crítico/validación/cierre presentes) | GO | GO | Ramón (pendiente) |
| 2026-08-08 | TERM | incompleto | S — faltan MÍNIMOS, VALIDACIÓN, NO HACER y criterio de cierre verificable ("cierre: los campos existen" viola §48) | GO CON CAMBIOS | GO CON CAMBIOS | Ramón (pendiente) |
| 2026-08-08 | TERM | contradictorio | S — contradice ADR-007 (núcleo congelado: sin ADR no se modifica) y asume `core/config.py` existente (fue eliminado post-F8; fuente es motor/core/config.py); además renombrar API pública viola semantic freezing | NO-GO | NO-GO | Ramón (pendiente) |
| 2026-08-08 | TERM | fase_futura | S — trabajo de F4 (panel+BD+servidor) durante F3; viola obligación 9 (trabajo prematuro) y §20/§47 (anti-sobreingeniería: BD+servidor sin necesidad) | NO-GO | NO-GO | Ramón (pendiente) |

**Resultado TERM (2026-08-08)**: 3/3 defectos esperados detectados (el plan correcto no tiene defecto por diseño) + veredictos correctos → **100% en defectos, 4/4 veredictos correctos**. Pendiente validación humana (Ramón) para cierre formal de B2.
