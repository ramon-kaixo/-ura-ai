---
description: "Verificación completa: revisor + verificador + tester sobre el estado actual del repo"
agent: build
---

Ejecuta verificación completa en tres fases secuenciales:

## Fase 1: Revisor (@revisor)
Audita el plan/código actual. Emite veredicto: GO / GO CON CAMBIOS / NO-GO.
Busca: problemas de arquitectura, seguridad, deuda técnica, regresiones.

## Fase 2: Verificador (@verificador)
Ejecuta los gates definidos en gates.json (ruff, mypy, pytest, secret-scan).
Reporta evidencia literal de cada gate.

## Fase 3: Tester (@tester)
Verifica que los tests son reales (RED→GREEN), no se debilitaron.
Valida cobertura ≥80% por módulo nuevo.

---
Ejecuta las tres fases secuencialmente y reporta resultado consolidado.
