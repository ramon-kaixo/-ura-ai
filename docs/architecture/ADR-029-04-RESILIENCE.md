# ADR-029-04: Resiliencia

**Estado:** Draft
**Fecha:** 2026-07-19
**Fase:** F29 — Bloque B5
**Dependencias:** ADR-029-01 (Observabilidad), ADR-029-03 (Operación)
**Prerrequisito:** F28.1 estable (protocolo fiable para circuit breakers)

---

## Contexto

La plataforma no tiene protección contra fallos:

- **Sin circuit breakers**: Un fallo en F26 Memory propaga el error a F25 y F24 (cascada)
- **Sin backpressure**: F25 puede saturar F26 con peticiones (OOM)
- **Sin degradación graceful**: Si F26 falla, F24—F25 deberían seguir operando sin persistencia
- **Sin chaos testing**: No se sabe cómo se comporta el sistema bajo fallo real

---

## Opciones Consideradas

### Opción A: Resiliencia completa desde el inicio
- **Ventaja:** Cobertura total.
- **Desventaja:** Puede endurecer comportamientos que B2/B3 revelen como incorrectos. Sobrecarga de mantenimiento.
- **Veredicto:** ❌ Rechazado.

### Opción B: Chaos tests primero, resiliencia después (SELECCIONADA)
- **Razonamiento:** Los chaos tests revelan qué protecciones son realmente necesarias. Se aplica el principio de "validación antes que endurecimiento" igual que en B2/B3.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Implementar chaos tests primero (7 escenarios), documentar los hallazgos, y solo entonces implementar las protecciones necesarias.

### Fase 1: Chaos Tests (antes de implementar protecciones)

| CT | Escenario | Acción | Qué observa |
|----|-----------|--------|-------------|
| 1 | Journal corrupto (F26) | Corromper línea aleatoria en journal | ¿Recuperación graceful? ¿Resto del log intacto? |
| 2 | Snapshot faltante (F26) | Eliminar archivo de snapshot | ¿Reconstrucción desde Journal? |
| 3 | Scheduler kill (F27) | `kill -9` del scheduler | ¿Cola preservada? ¿Reinicio limpio? |
| 4 | Componente inalcanzable | Desconectar adaptador de protocolo | ¿Circuit breaker se abre? ¿Degradación graceful? |
| 5 | Disco lleno simulado | Llenar Filesystem hasta 100% | ¿Error graceful? ¿Crash? |
| 6 | Latencia extrema | Añadir sleep(10s) en adaptador | ¿Timeout? ¿Circuit breaker? |
| 7 | Reinicio en caliente | `kill -HUP` del proceso principal | ¿Graceful shutdown + restart limpio? |

**Formato de salida:** Para cada CT, documentar: escenario, comportamiento esperado vs observado, pérdida de datos, tiempo de recuperación.

### Fase 2: Protecciones (solo las necesarias según CT)

Basado en los hallazgos de los chaos tests, se implementan:

| Protección | Disparada por CT | Implementación |
|-----------|-----------------|----------------|
| Circuit breaker F24→F25 | CT-4 | Wrapper en adaptador F28 |
| Circuit breaker F25→F26 | CT-4, CT-6 | Wrapper en adaptador F28 |
| Backpressure F25→F26 | CT-5 | Cola acotada + semáforo |
| Degradación graceful sin F26 | CT-1, CT-2 | F24—F25 operan sin persistencia |
| Timeouts configurables | CT-6 | Por llamada cross-component |
| Journal auto-repair F26 | CT-1 | Skip línea corrupta, reportar |

---

## Consecuencias

**Positivas:**
- Las protecciones se implementan basadas en evidencia, no en teoría
- Los chaos tests son reproducibles (se pueden ejecutar en CI)
- La degradación graceful está documentada ANTES de necesitarla

**Negativas:**
- Los chaos tests requieren tiempo de ejecución (~3-5h total)
- Algunos CT pueden requerir entorno específico (disco lleno)
- Las protecciones pueden ser más simples de lo esperado (o más complejas)

**Neutras:**
- Los CT reutilizan los wrappers de protocolo de F28.1
- F26 Memory ya tiene auto-recovery (journal skip) — solo verificar

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| R01 | Todo CT documenta expected vs observed | Informe CT |
| R02 | Ningún CT causa pérdida de datos no documentada | Post-CT verificación |
| R03 | Tiempo de recuperación documentado por CT | Informe CT |
| R04 | Circuit breakers implementados en todas las llamadas cross-component | Revisión de código |
| R05 | Backpressure implementada donde los CT revelaron necesidad | Informe CT |
| R06 | Degradación graceful sin F26 documentada y testeada | CT-1, CT-2 |
| R07 | Todos los CT ejecutables en 1 comando | Script de chaos |
| R08 | Sin cambios en APIs públicas | Diff de interfaz |
