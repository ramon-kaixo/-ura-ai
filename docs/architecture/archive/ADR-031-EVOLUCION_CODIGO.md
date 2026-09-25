# ADR-031: Evolución del Código — Reuso, Calidad y Consolidación

**Estado:** Aprobado  
**Fecha:** 2026-07-20  
**Depende de:** ADR-030 (infraestructura congelada)

---

## Contexto

El proyecto ha alcanzado un nivel de complejidad donde la duplicación
de código y la falta de consolidación periódica pueden degradar la
arquitectura más rápido de lo que las nuevas capacidades la mejoran.

El Reuse Detector y los Quality Gates proporcionan mecanismos para
detectar duplicación y disparar ciclos de consolidación.

## Decisión

### 1. Consulta obligatoria al índice de reutilización

Toda nueva funcionalidad debe consultar primero el índice de
reutilización (`ReuseDetector.search()` o `analyze_new_code()`).

Si existe una implementación similar por encima del umbral del **85%**,
debe justificarse por escrito (en el commit message o en una entrada
del ExecutionLedger) por qué no se reutiliza.

**Excepción:** Scripts de una sola ejecución, tests, documentación.

### 2. Quality Gates obligatorios antes de promoción

Antes de promocionar cambios a producción, deben ejecutarse los
Quality Gates (`consolidacion.py --check`).

Si se superan los umbrales (10+ commits o 2000+ líneas desde el
último tag), debe ejecutarse el ciclo completo de consolidación
(`consolidacion.py --force`).

### 3. Registro de excepciones

Toda excepción a las reglas 1 y 2 debe registrarse en el
ExecutionLedger mediante `add_decision()` con tipo `adr031_exception`.

### 4. Ciclo de consolidación periódico

El ciclo de consolidación debe ejecutarse al menos cada 15 commits
o 2000 líneas modificadas, lo que ocurra primero. El temporizador
systemd (`ura-maintenance-v2.timer`) sigue siendo el mecanismo de
ejecución base, pero los Quality Gates añaden disparadores
adicionales por actividad del repositorio.

## Umbrales

| Regla | Umbral | Acción |
|-------|--------|--------|
| Reutilización | ≥ 85% similitud | Justificar por qué no se reusa |
| Quality Gates | 10+ commits o 2000+ líneas | Ejecutar consolidación --force |
| Excepciones | Cualquiera | Registrar en ExecutionLedger |

## Archivos afectados

| Componente | Archivo | Cambio |
|-----------|---------|--------|
| Reuse Detector | `scripts/pro/reuse/` | Consulta obligatoria ante nuevo código |
| Quality Gates | `scripts/pro/reuse/quality_gates.py` | Disparador pre-promoción |
| Consolidación | `scripts/pro/consolidacion.py` | Ciclo completo al superar umbrales |
| ExecutionLedger | `scripts/pro/tuneladora/ledger.py` | Registro de excepciones vía add_decision() |

## Incumplimiento

Si no se cumple esta ADR, la deuda técnica acumulada puede:

1. Duplicar funcionalidad existente sin beneficiar al sistema
2. Degradar la arquitectura por falta de consolidación
3. Aumentar el coste de mantenimiento a largo plazo
