# ADR-029-06: Gobernanza

**Estado:** Approved
**Fecha:** 2026-07-20
**Fase:** F29 — Bloque B7
**Dependencias:** B2—B6 completos (los runbooks y SLOs se basan en datos reales)

---

## Contexto

La plataforma carece de gobernanza operativa:

- **Sin ownership documentado**: No hay una matriz que asigne responsable por componente
- **Sin runbooks**: Dependencia de una sola persona para operar el sistema
- **Sin release checklist**: Los releases se hacen manualmente, sin verificación sistemática
- **Sin SLOs**: No hay objetivo de calidad medible
- **ADRs F29 pendientes**: Los 5 ADRs de F29 están en Draft al inicio de la fase

---

## Opciones Consideradas

### Opción A: Escribir runbooks al inicio de F29
- **Riesgo:** Los runbooks cambiarían después de B2/B3/B4/B5/B6. Trabajo perdido.
- **Veredicto:** ❌ Rechazado.

### Opción B: Escribir runbooks al final de F29, basados en experiencia real (SELECCIONADA)
- **Razonamiento:** B2—B6 generan conocimiento operativo real. Los runbooks escritos después reflejan la realidad, no suposiciones.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Escribir toda la gobernanza AL FINAL de F29, después de que B2—B6 hayan generado experiencia operativa real.

### Artefactos a producir

| Artefacto | Contenido | Fuente de datos |
|-----------|-----------|-----------------|
| Matriz de propiedad | Componente, productor, consumidor, owner, source of truth | Arquitectura F24—F28 |
| Runbook: Arranque | Orden de inicio, verificación post-arranque | Experiencia de B4 |
| Runbook: Parada | Graceful shutdown, verificación de datos | B4 implementación |
| Runbook: Recuperación | Restaurar F26 desde backup, verificar integridad | B4 implementación + B5 chaos tests |
| Runbook: Degradación | Qué hacer cuando un componente falla | B5 chaos tests |
| Runbook: Incidente | Detección, diagnóstico, escalado, post-mortem | B5 chaos tests |
| Release checklist | Automatizado en CI | Lista de verificación + B6 compat |
| SLOs y error budgets | Targets basados en métricas reales | B2 benchmarks, B1 métricas |
| ADRs F29 | 029-01..06: Draft → Approved | Experiencia de toda la fase |

### Formato de Runbook

Cada runbook sigue esta plantilla:

```markdown
## Runbook: [Nombre]

### Propósito
[Qué problema resuelve]

### Cuándo se usa
[Condiciones de activación]

### Procedimiento
1. [Paso con comando]
2. [Paso con comando]
3. [...]

### Verificación
[Cómo confirmar que funcionó]

### Responsable
[Equipo/persona]

### Tiempo estimado
[Minutos]
```

### SLOs y Error Budgets

Basados en métricas reales de B2:

| SLO | Target | Ventana | Fuente de métrica |
|-----|--------|---------|-------------------|
| Disponibilidad health endpoint | 99.9% | 30d | Prometheus |
| Durabilidad F26 | 100% (fsync por escritura) | 30d | Journal checksums |
| Throughput F27 | X ejecuciones/hora | 1h | B2 benchmark |
| Latencia F24 búsqueda p95 | <X s | 1h | B2 benchmark |
| Error rate cross-component | <Y% | 1h | B1 metrics |
| Recuperación F26 tras fallo | <Z min | Por evento | B5 chaos test |

Los valores X, Y, Z se determinan después de B2.

---

## Consecuencias

**Positivas:**
- Runbooks basados en experiencia real, no en teoría
- SLOs con targets realistas (medidos en B2)
- Sin trabajo perdido por cambios durante la fase
- La matriz de propiedad puede escribirse en cualquier momento (no depende de B2—B6)

**Negativas:**
- No hay runbooks durante B2—B6 (pero B2—B6 son experimentales, no operación real)
- La fase no produce runbooks hasta el final

**Neutras:**
- La matriz de propiedad se escribe al inicio de B7 (no depende de experimentos)
- Los ADRs F29 se promueven a Approved al final, con la experiencia de toda la fase

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| G01 | Matriz de propiedad cubre F24—F29 | Revisión manual |
| G02 | Cada runbook tiene procedimiento paso a paso verificable | Revisión |
| G03 | Release checklist automatizado en CI | CI config |
| G04 | SLOs con targets basados en B2 benchmarks | Documentado |
| G05 | 5 ADRs F29 en estado Approved | Revisión |
| G06 | Runbooks escritos después de B5 (no antes) | Fechas |
