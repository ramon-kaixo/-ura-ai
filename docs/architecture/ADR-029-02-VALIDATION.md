# ADR-029-02: Validación — Técnica y Funcional

**Estado:** Draft
**Fecha:** 2026-07-19
**Fase:** F29 — Bloques B2 + B3
**Dependencias:** ADR-029-01 (Observabilidad — necesario para medir)
**Prerrequisito:** F28.1 estable

---

## Contexto

La plataforma tiene 907 tests en F24—F28 pero **cero validación con datos reales**.

Los tests existentes demuestran:
- Cobertura de código
- Corrección de invariantes
- Comportamiento bajo condiciones controladas

NO demuestran:
- Utilidad para problemas reales
- Rendimiento con cargas representativas
- Calidad del conocimiento fusionado
- Precisión en dominios especializados

---

## Opciones Consideradas

### Opción A: Validación solo técnica (benchmarks sintéticos)
- **Ventaja:** Rápido, reproducible, automatizable.
- **Desventaja:** No detecta problemas de calidad real (facts incorrectos, contexto irrelevante).
- **Veredicto:** ❌ Rechazado. Se necesita ambos.

### Opción B: Validación solo funcional (casos reales)
- **Ventaja:** Mide utilidad real.
- **Desventaja:** Sin benchmarks no hay baseline de rendimiento. Los problemas de throughput aparecen en producción.
- **Veredicto:** ❌ Rechazado.

### Opción C: Validación técnica primero, funcional después (SELECCIONADA)
- **Razonamiento:** Primero se caracteriza el rendimiento (B2), luego se valida la utilidad (B3). B2 proporciona métricas de referencia para interpretar B3.
- **Veredicto:** ✅ Seleccionada.

---

## Decisión

Dividir validación en dos sub-bloques ejecutados secuencialmente.

### B2 — Validación Técnica

**Objetivo:** Caracterizar rendimiento con datos controlados.

| Prueba | Pipeline | Métricas |
|--------|----------|----------|
| Throughput F24 | WebPipeline.search() | docs/s, latencia p50/p95/p99 |
| Throughput F25 | FusionPipeline.run() | claims/s, facts/s, latencia por stage |
| Throughput F26 | Memory.append() + state_at() | entradas/s, consultas/s |
| Throughput F27 | Scheduler.submit() | ejecuciones/s, tiempo en cola |
| Cadena completa | F24→F25→F26 (+ F27 opcional) | Throughput end-to-end, cuello de botella |
| Memoria | Cada componente aislado | RSS, pico, leak (1000+ ops) |
| Precisión F25 | Corpus conocido | Precision, Recall, F1 |
| Estrés | 10x throughput normal | Punto de saturación, degradación |

**Formato de salida:** Para cada prueba, un CSV/JSON con resultados + una sección en el informe técnico.

**Criterio:** Resultados publicados en `docs/architecture/F29_B2_BENCHMARKS.md`.

### B3 — Validación Funcional

**Objetivo:** Demostrar utilidad en 5 dominios reales.

| Dominio | Documentos | Pipeline | Qué mide |
|---------|-----------|----------|----------|
| Jurídico | 20 sentencias/contratos (anónimos) | F24→F25→F26 | Precisión extracción, coherencia facts |
| Técnico | Documentación APIs, manuales | F24→F25→F26 | Calidad fusión, desambiguación entidades |
| Código | 2 repositorios grandes | F24→F25→F26 | Escalabilidad, capacidad contexto |
| Científico | 20 artículos open access | F24→F25→F26 | Precisión relaciones, entidades |
| Conversacional | 10 diálogos largos | F26→F27 | Memoria contextual, coherencia temporal |

**Métricas de utilidad (no rendimiento):**
- Precisión del fact extraído (revisión manual de muestra)
- Coherencia temporal (F26): facts recuperados consistentes en el tiempo
- Utilidad del contexto (F27): agente produce mejores respuestas con contexto histórico
- Tasa de error real: cuántos facts son incorrectos

**Formato de salida:** 5 informes de una página cada uno, uno por dominio, en `docs/architecture/F29_B3_REPORTS/`.

---

## Consecuencias

**Positivas:**
- La validación técnica descubre cuellos de botella ANTES de endurecer (B5)
- La validación funcional guía las prioridades de operación (B4)
- Los informes son evidencia objetiva de utilidad

**Negativas:**
- B3 requiere ~20h, es el bloque más grande de F29
- Algunos dominios pueden revelar problemas que requieran volver a B2

**Neutras:**
- Los datasets deben ser públicos o anónimos (no datos sensibles)
- Los informes se escriben en español, igual que el resto de la documentación

---

## Invariantes

| ID | Invariante | Verificación |
|----|-----------|-------------|
| V01 | B2 produce métricas de throughput, latencia y memoria para cada subsistema | CSV informes |
| V02 | B2 incluye al menos 1 test de estrés (10x throughput) | Resultados |
| V03 | B3 procesa ≥20 documentos por dominio | 5 informes |
| V04 | B3 incluye revisión manual de ≥10% de los facts generados | Informe |
| V05 | Todos los datasets son públicos o anónimos | Documentado |
| V06 | Cada informe B3 tiene una sección de "hallazgos inesperados" | Informe |
| V07 | B2 completo antes de empezar B3 | Orden de ejecución |

---

## Formatos de Salida

### Informe Técnico (B2)
```markdown
# F29 B2 — Validación Técnica

## Resumen
- Throughput máximo: X docs/s (F24), Y facts/s (F25), Z entradas/s (F26)
- Cuello de botella: [Componente]
- Memoria pico: [Valor]

## Resultados por prueba
| Prueba | Valor | P50 | P95 | P99 |
|--------|-------|-----|-----|-----|
| ... | ... | ... | ... | ... |

## Punto de saturación
- A partir de X requests/s, la latencia crece no linealmente
- El componente limitante es [Componente]
```

### Informe Funcional (B3)
```markdown
# F29 B3 — Validación Funcional: [Dominio]

## Dataset
- 20 documentos de [fuente]
- Rango de tamaños: [min-max] palabras

## Resultados
- Facts generados: X
- Precisión estimada: Y% (revisión manual de Z facts)
- Coherencia temporal: [Bien/Regular/Mal]
- Hallazgos inesperados: [Lista]

## Conclusión
- La plataforma [sí/no] es útil para este dominio
- Limitaciones: [Lista]
```
