# ADR-012-01: Contrato de Calidad — Métricas de Recuperación y Razonamiento

> **Fecha:** 2026-07-05
> **Fase:** 12 (Inteligencia)
> **Propósito:** Definir las métricas objetivas que evaluarán la calidad del
> Knowledge Engine 2.0 y el sistema multiagente, así como el corpus de
> evaluación mínimo exigible antes de aceptar cualquier mejora como válida.
> **Estado:** ✅ Aprobado

## Contexto

Hasta F11, la validación se centró en métricas de infraestructura:

| Métrica | Mide |
|---------|------|
| pytest | Integridad funcional |
| ruff | Calidad del código |
| Cobertura | Ejercicio de componentes |
| Benchmarks | Degradación de rendimiento |

En F12 aparecen métricas de **calidad del resultado** que ninguna de las
anteriores captura. Un KE 2.0 puede pasar todos los tests, tener 100% de
cobertura y responder en 50ms, pero devolver resultados irrelevantes.

Sin un contrato de calidad explícito, no hay forma objetiva de:
- Aceptar o rechazar una mejora algorítmica
- Comparar KE 2.0 vs KE 1.x
- Detectar regresiones en precisión
- Justificar trade-offs (más latencia por mejor recall)

## Decisión

### 1. Corpus de Evaluación Mínimo

Toda evaluación de KE 2.0 requiere un corpus con estas características:

| Dimensión | Requisito mínimo |
|-----------|-----------------|
| Consultas | ≥ 200 pares (query, chunk_relevante, docs_relevantes) |
| Dominios | ≥ 3 (ej. código, documentación técnica, conversaciones) |
| Anotación | Cada consulta tiene 1 chunk "golden" + N chunks relevantes (N ≥ 3) |
| Formato | JSON Lines: `{"query": "...", "golden": "...", "relevant": ["...", ...], "domain": "..."}` |
| Versionado | El corpus vive en `knowledge/benchmark/` con tag semántico |

El corpus se genera a partir de:
1. Consultas reales del historial (≥ 60%)
2. Consultas sintéticas de bordes (≥ 20%): queries ambiguas, muy cortas, vacías
3. Consultas adversariales (≥ 10%): queries diseñadas para confundir al ranker
4. Consultas multi-turno (≥ 10%): preguntas que requieren contexto previo

Este corpus **es requisito de entrada** para cualquier trabajo en KE 2.0.
Sin él, no se puede validar una mejora.

### 2. Métricas de Calidad

#### 2.1 Métricas de Recuperación (Ranking)

| Métrica | Fórmula | Objetivo KE 2.0 | Cuándo medir |
|---------|---------|-----------------|--------------|
| **Recall@k** | `#relevant_in_top_k / #total_relevant` | ≥ 0.85 @ k=10 | Cada cambio en ranking |
| **Precision@k** | `#relevant_in_top_k / k` | ≥ 0.60 @ k=10 | Cada cambio en ranking |
| **MRR** | Mean Reciprocal Rank del primer relevante | ≥ 0.75 | Cada cambio en ranking |
| **nDCG@k** | Normalized Discounted Cumulative Gain | ≥ baseline + 20% | Cada cambio en ranking |
| **MAP** | Mean Average Precision | ≥ 0.65 | Cada release |

#### 2.2 Métricas de Latencia

| Métrica | Objetivo | Umbral de alerta |
|---------|----------|------------------|
| **P50 búsqueda** | ≤ 150ms | > 200ms |
| **P95 búsqueda** | ≤ 500ms | > 750ms |
| **P99 búsqueda** | ≤ 2s | > 3s |
| **P50 reranking** | ≤ 500ms | > 750ms |
| **P95 reranking** | ≤ 2s | > 3s |
| **P50 chunking** | ≤ 50ms por doc | > 100ms |

#### 2.3 Métricas de Cobertura

| Métrica | Definición | Objetivo |
|---------|------------|----------|
| **Tasa de respuesta sin contexto** | Queries donde el chunk más similar tiene score < 0.6 | ≤ 5% |
| **Cobertura de documentos recuperados** | % del corpus que alguna vez aparece en top-100 | ≥ 80% |
| **Diversidad de fuentes** | Nº medio de documentos distintos en top-10 | ≥ 3 |

#### 2.4 Métricas de Reranking

| Métrica | Definición | Objetivo |
|---------|------------|----------|
| **nDCG uplift** | nDCG@10 después de reranker - nDCG@10 antes | ≥ +0.10 |
| **Re-rank latency overhead** | Tiempo extra del cross-encoder sobre top-K | ≤ 1.5s P95 |

#### 2.5 Métricas de Sistema Multiagente

| Métrica | Definición | Objetivo |
|---------|------------|----------|
| **Tasa de finalización** | % de tareas completadas sin intervención | ≥ 85% |
| **Precisión del validador** | % de veces que validador acepta respuesta correcta | ≥ 90% |
| **Eficiencia del planner** | Nº de subtareas generadas vs óptimo esperado | ≤ 2x |
| **Consenso** | % de acuerdos Mayoría vs ground truth | ≥ 80% |

### 3. Procedimiento de Validación

Todo cambio que afecte a la calidad de recuperación debe pasar por:

```
1. Extraer corpus de evaluación (→ benchmark.jsonl)
2. Ejecutar baseline (KE 1.x actual):
   - metrics_baseline.json
3. Ejecutar con el cambio:
   - metrics_candidate.json
4. Comparar métricas:
   - ¿Recall@10 mejoró o se mantuvo?
   - ¿Latencia P95 dentro del umbral?
   - ¿nDCG uplift positivo?
5. Si hay degradación en alguna métrica:
   - Documentar trade-off y justificar
6. Si todo OK → commit
```

Este procedimiento se ejecuta con:

```bash
python3 scripts/pro/benchmark_ke_quality.py \
    --corpus knowledge/benchmark/v1.jsonl \
    --output knowledge/benchmark/results/
```

### 4. Baseline KE 1.x

El baseline contra el que se compara KE 2.0 es el sistema actual:

| Componente | KE 1.x |
|------------|--------|
| Chunking | Por tokens fijos (512 tokens, overlap 64) |
| Embeddings | nomic-embed-text via Ollama |
| Index | Qdrant (cosine similarity) |
| Ranking | Cosine similarity únicamente |
| Reranking | No existe |
| Retrieval | Single-stage (solo vectorial) |

**Métricas baseline (a medir antes de iniciar KE 2.0):**

Se ejecuta `benchmark_ke_quality.py --corpus v1 --output baseline/` y se
almacena el resultado en `knowledge/benchmark/baseline_ke1.json`.

KE 2.0 debe superar estas métricas en todos los indicadores de calidad.
Donde no sea posible (trade-off latencia vs recall), debe documentarse.

### 5. Aceptación de Mejoras

| Escenario | Decisión |
|-----------|----------|
| Recall@10 mejora ≥ 5%, latencia igual | ✅ Aceptado |
| Recall@10 mejora ≥ 10%, latencia P95 +20% | ✅ Aceptado (trade-off documentado) |
| Recall@10 igual, latencia -30% | ✅ Aceptado (optimización) |
| Recall@10 empeora ≥ 3% (cualquier latencia) | ❌ Rechazado |
| nDCG uplift negativo | ❌ Rechazado |
| Tasa de "sin contexto" > 5% | ❌ Rechazado |

## Consecuencias

### Positivas
- Las mejoras se evalúan con datos, no con opiniones
- El corpus de evaluación es un activo reutilizable
- Las regresiones se detectan automáticamente
- Los trade-offs quedan documentados

### Negativas
- Crear el corpus de 200 consultas requiere trabajo inicial (estimado: 2-3h)
- Las evaluaciones llevan tiempo (ejecutar benchmark completo: ~5-10 min)
- El corpus puede tener sesgo si no se diversifica

## Implementación Inmediata

1. Crear `knowledge/benchmark/` directorio
2. Implementar `scripts/pro/benchmark_ke_quality.py` (herramienta de evaluación)
3. Población inicial del corpus (200 consultas)
4. Ejecutar baseline KE 1.x
5. Documentar métricas baseline en `knowledge/benchmark/baseline_ke1.json`

Este paso es **requisito obligatorio** antes de cualquier desarrollo de KE 2.0.
