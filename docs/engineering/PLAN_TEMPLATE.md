<!-- PLAN_TEMPLATE v1.0 — Engineering Process -->

# PLAN_TEMPLATE — Cómo preparar un plan

Todo plan nuevo responde obligatoriamente a estas 11 preguntas. La sección de cabecera identifica el plan; el resto son secciones con título fijo. Un plan sin estas secciones está incompleto.

## Cabecera

- **Título**: `<NOMBRE DEL PLAN> vX.Y`
- **Estado**: PROPUESTO / APROBADO / EN EJECUCIÓN / CERRADO
- **Fecha**: YYYY-MM-DD
- **Versión**: semver
- **Autor / Solicitante**: [RAMON|WEB|TERM]

## 1. ¿QUÉ QUIERO CONSEGUIR? (Objetivo)

Resultado final concreto y verificable. Un párrafo + bullet de entregables.

## 2. ¿POR QUÉ? (Intención / Problema)

Qué problema resuelve, qué motivación existe, qué consecuencias tiene no hacerlo.

## 3. ¿QUÉ CONTEXTO EXISTE?

Estado real del proyecto: git, arquitectura, código relacionado, ADRs, planes previos, closeouts, decisiones, tests, configuración, restricciones conocidas, documentación. (El agente verificará esto contra el código; el plan no debe asumir que el autor tiene razón.)

## 4. ¿QUÉ TIENE QUE HACER? (Alcance / Cambios)

Qué archivos/zona se tocan, qué funcionalidad se añade/cambia. Identificar ARCHIVOS / ZONAS DE TRABAJO para reservas.

## 5. ¿QUÉ ES MÍNIMO? (Mínimos obligatorios)

Condiciones que sí o sí se cumplen para dar por terminado. Si un mínimo no puede cumplirse, el trabajo NO está terminado.

## 6. ¿QUÉ ES CRÍTICO? (Puntos críticos / Invariantes)

Lo que no debe perderse aunque cambie la implementación: trazabilidad, contexto, seguridad, compatibilidad, reversibilidad, contratos, documentación, integridad, ausencia de regresiones.

## 7. ¿CÓMO DEBE COMPORTARSE? (Comportamiento esperado)

Cómo se comporta el sistema después del cambio (no solo qué archivos modificar).

## 8. ¿QUÉ NO DEBE HACER? (NO HACER)

Zonas que no tocar; funcionalidades que no implementar; fases que no adelantar; dependencias que no introducir; decisiones que no cambiar; comportamientos que no modificar; mejoras no autorizadas.

## 9. ¿QUÉ ESTÁ FUERA DE ALCANCE?

Lo que este plan NO cubre, explícitamente. Si se necesita, será otro plan o una fase posterior.

## 10. ¿CÓMO SE VALIDARÁ? (Validación)

Cómo se demuestra que funciona: tests, checks, pruebas manuales, comprobaciones, criterios de aceptación.

## 11. ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO? (Criterios de cierre)

Checklist verificable de cierre (parecido al §48 del Plan 0: evidencia, no "los archivos existen").

---

*Nota: al entregar el plan a un agente, este lo analizará (PLAN_REVIEW_TEMPLATE.md) y añadirá sus 9 preguntas (qué falta, qué está mal, contradicciones, riesgos, casos extremos, simplificaciones, mejoras, qué no deberíamos hacer, qué pertenece a otra fase). El veredicto (GO / GO CON CAMBIOS / NO-GO) es valoración técnica; la decisión la toma el coordinador humano.*
