<!-- PLAN_REVIEW_TEMPLATE v1.0 — Engineering Process -->

# PLAN_REVIEW_TEMPLATE — Cómo debe analizar el plan el agente

Antes de ejecutar CUALQUIER plan, el agente produce este análisis. No es burocracia: es la obligación central de la metodología (un plan nunca se ejecuta sin análisis previo). Si el trabajo se coordina por UDO, este análisis se registra en el expediente (campo `analisis:` del expediente — PLAN 1 A1).

**Proporcionalidad (PLAN 1 B4)**: el análisis debe ser proporcional al riesgo del plan. Plan trivial (cosmético, doc, refactor pequeño) → análisis breve de 5-10 líneas en el campo `analisis:`. Plan complejo (arquitectura, contratos, fases completas) → análisis completo con esta plantilla y veredicto.

## 1. ANÁLISIS DEL PLAN

| Sección | Contenido |
|---------|-----------|
| Qué entiendo | Resumen de la intención y el objetivo (distinguir objetivo real de método propuesto) |
| Qué he comprobado | Verificaciones hechas contra el código real (git, archivos, tests, ADRs, config) |
| Qué coincide | Partes del plan que describen correctamente la realidad |
| Qué falta | Omisiones: requisitos, archivos, tests, casos extremos, integración, seguridad, operación |
| Qué contradicciones existen | Plan vs código vs documentación vs decisiones anteriores |
| Qué riesgos existen | Funcionales, seguridad, concurrencia, recursos, arquitectura, operación, mantenimiento |
| Qué casos extremos existen | Degradación, agentes parados, conflictos, fallos parciales, reanudación |
| Qué cambiaría | Propuesta de plan corregido (modificaciones concretas) |
| Qué no tocaría | Zonas/decisiones/contratos que el plan debe respetar |
| Qué es obligatorio | Lo que no se puede omitir (mínimos, puntos críticos) |
| Qué es opcional | Mejoras distinguidas de requisitos (clasificación: NECESARIO/MEJORA/DESCUBRIMIENTO) |
| Qué pertenece a otra fase | Trabajo prematuro — señalarlo, NO implementarlo |
| Propuesta de plan corregido | El plan resultante de incorporar los hallazgos |
| Valoración final | Síntesis y veredicto |

## 2. VEREDICTO

| Veredicto | Significado |
|-----------|-------------|
| **GO** | El plan es suficientemente sólido para ejecutar. |
| **GO CON CAMBIOS** | Hay modificaciones que deben incorporarse antes. |
| **NO-GO** | Existe un problema que impide ejecutar correctamente. |

El veredicto es **valoración técnica para el coordinador humano**, no autorización automática. Con GO CON CAMBIOS o NO-GO, el plan revisado vuelve al solicitante.

## 3. Clasificación de descubrimientos (anexo)

Todo descubrimiento del análisis se clasifica según la directiva permanente (`docs/udo/REGLA-PLAN-MINIMOS-DESCUBRIMIENTOS.md`) y el Engineering Process §4:

OBLIGATORIO / NECESARIO / MEJORA / DESCUBRIMIENTO / PENDIENTE / FUERA DE ALCANCE

Cada ítem: qué es, por qué, clase, decisión propuesta. La clasificación evita convertir cada hallazgo en trabajo nuevo.

## 4. Regla de honestidad

- Si no se pudo verificar algo: decirlo explícitamente ("NO VERIFICADO"), no inventar.
- Si la revisión la hace el mismo agente que ejecuta: marcarla como AUTO-REVISIÓN (la herramienta UDO lo hace automáticamente).
- Nunca fingir una revisión independiente que no ocurrió.

---

*Uso: 1) recibir plan → 2) completar §1 → 3) emitir veredicto §2 → 4) si GO CON CAMBIOS/NO-GO, devolver plan corregido → 5) tras aprobación humana, ejecutar (reservas → ejecución → commits → validación → revisión → cierre).*
