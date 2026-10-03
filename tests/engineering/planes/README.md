# Prueba de Eficacia Conductual (Plan 1 B2)

## Objetivo
Validar que un agente (TERM o WEB) detecta defectos en planes usando la metodología URA.

## 4 Planes de ejemplo
| Archivo | Tipo | Defecto esperado |
|---------|------|------------------|
|  | Correcto | Ninguno (GO) |
|  | Incompleto | Faltan secciones obligatorias (NO-GO) |
|  | Contradictorio | Viola ADR-003 congelado (NO-GO) |
|  | Fase futura | Trabajo prematuro F15 en F9 (NO-GO) |

## Procedimiento de evaluación
1. El agente recibe UNO de los 4 planes (sin saber cuál es)
2. El agente produce **ANÁLISIS DEL PLAN** completo (según )
3. El agente emite **VEREDICTO**: GO / GO CON CAMBIOS / NO-GO
4. Evaluador humano (Ramón) compara con defecto esperado

## Criterio de éxito
- **≥ 3 de 4** planes evaluados correctamente (defecto detectado + veredicto coherente)
- El plan correcto debe recibir GO
- Los 3 defectuosos deben recibir NO-GO (o GO CON CAMBIOS con defecto identificado)

## Registro de evaluación
Fecha | Agente | Plan evaluado | Veredicto | Defecto detectado | ✓/✗
------|--------|---------------|-----------|-------------------|-----

## Notas
- La prueba es **conductual** (evalúa comportamiento del LLM, no presencia de archivos)
- No se automatiza: requiere juicio humano sobre calidad del análisis
- Se ejecuta manualmente por Ramón o en revisión cruzada
