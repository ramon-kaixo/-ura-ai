# F24 — Closeout: Web Intelligence

**Versión:** v0.24.0
**Fecha:** 2026-07-17
**Estado:** ✅ Cerrada

---

## Resumen

F24 implementa el módulo de Web Intelligence (`motor/core/web/`), una cadena completa
de búsqueda, extracción, limpieza, deduplicación, ranking, resumen extractivo y
trazabilidad de fuentes.

8 bloques ejecutados en orden atómico (B1→B8), más benchmark y closeout (B9).

---

## Bloques

| Bloque | Archivos | Tests | Estado |
|--------|----------|-------|--------|
| **B1** Arquitectura | `base.py`, `models.py`, `pipeline.py`, `registry.py`, `config.py` | — | ✅ |
| **B2** Searchers | `searcher/providers/duckduckgo.py`, `searxng.py` | 15 | ✅ |
| **B3** Crawler | `crawler/providers/httpx_crawler.py` | 15 | ✅ |
| **B4** Extractor | `extractor/providers/html_extractor.py` | 26 | ✅ |
| **B5** Cleaner | `cleaner/cleaner.py`, `deduplication.py`, `url_utils.py` | 39 | ✅ |
| **B6** Ranker | `ranker/ranker.py` | 23 | ✅ |
| **B7** Summarizer | `summarizer/summarizer.py` | 24 | ✅ |
| **B8** Citations | `citation/citation.py` | 20 | ✅ |
| **B9** Benchmark | `scripts/pro/benchmark_f24.py`, e2e test | 4 | ✅ |

---

## Decisiones Arquitectónicas

### 1. Dos fases internas en el extractor HTML

`HtmlExtractor` separa limpieza DOM (`_clean_html`) de conversión a `WebDocument`
(`_to_webdocument`). Esto permite añadir extractores PDF/Markdown/DOCX sin alterar
el contrato del pipeline.

### 2. Tres estrategias de deduplicación

`DeduplicationEngine` aplica en orden: URL normalizada → document_id (canónica)
→ content_hash (SHA-256). Cada estrategia detecta un caso distinto de duplicado
y conserva el documento de mayor `quality_score`.

### 3. Ranking descomponible

`RankingScore` almacena las 9 contribuciones individuales (quality, position,
length, title_match, url_match, text_match, canonical_bonus, short_penalty,
empty_penalty). Esto permite en F25 justificar por qué una fuente fue priorizada
sin modificar el algoritmo.

### 4. Resumen extractivo sin modificación de texto

`ExtractiveSummarizer` selecciona frases literales del original. Cada frase del
resumen es copia exacta de una frase del documento fuente, lo que habilita la
trazabilidad en B8 sin alineamiento posterior.

### 5. Evidence ID estable

`evidence_id` = SHA-256(document_id:position:content_hash)[:16]. Permite
referirse a piezas concretas de evidencia desde Knowledge Fusion, memoria y
agentes sin depender de índices de listas.

### 6. Sin dependencias nuevas

Todo el módulo usa solo stdlib (`html.parser`, `urllib.parse`, `hashlib`,
`threading`, `dataclasses`, `re`, `math`, `json`). Las únicas excepciones son
`httpx` (crawler, ya presente en el proyecto) y `duckduckgo_search` (searcher,
ya presente).

---

## Métricas de Benchmark

| Métrica | Valor |
|---------|-------|
| Throughput | 5.477 docs/s |
| Tiempo total medio | 1,28 ms |
| Documentos de entrada | 7 |
| Documentos válidos tras limpieza + dedup | 5 |
| Duplicados eliminados | 2 (28,6%) |
| Citas generadas | 8 |
| Evidencia única | 8 |
| Compresión del resumen | 59,8% |

### Latencia por etapa (P50)

| Etapa | P50 | P95 |
|-------|-----|-----|
| Extract | 0,5 ms | 0,5 ms |
| Clean | <0,1 ms | <0,1 ms |
| Dedup | 0,1 ms | 0,1 ms |
| Rank | 0,1 ms | 0,1 ms |
| Summarize | 0,5 ms | 0,5 ms |
| Cite | 0,1 ms | 0,1 ms |

---

## Tests

- **580 tests totales** (0 regresiones vs v1.0.0)
- 162 tests nuevos en F24
- Test end-to-end determinista (`test_pipeline_e2e.py`) sin acceso a Internet
- 0 flaky tests (determinismo garantizado por `sys.modules` restoration)

### Cobertura funcional

| Componente | Tests |
|------------|-------|
| DuckDuckGoSearchProvider | 15 |
| HttpCrawler (con SSRF) | 15 |
| HtmlExtractor | 26 |
| DocumentCleaner + url_utils | 39 |
| DeduplicationEngine | (incluido en cleaner) |
| DocumentRanker + RankingScore | 23 |
| ExtractiveSummarizer | 24 |
| CitationEngine + Evidence | 20 |
| Pipeline E2E | 4 |

---

## Checklist de Validación

| # | Check | Resultado |
|---|-------|-----------|
| 1 | `py_compile` 0 errores en todos los módulos tocados | ✅ |
| 2 | `ruff check` 0 errores nuevos vs baseline | ✅ |
| 3 | `pytest` mismo resultado que baseline (0 regresiones) | ✅ (580 passed) |
| 4 | Smoke test benchmark | ✅ (3 iteraciones) |
| 5 | Test E2E determinista | ✅ (4/4) |
| 6 | Memoria: sin fugas evidentes (GC de Python) | ✅ |
| 7 | Benchmark reproducible desde CLI | ✅ |
| 8 | Exportación JSON de resultados | ✅ |
| 9 | `git status` sin cambios sin commitear | Pendiente |
| 10 | Tag de versión `v0.24.0-fase24` | Pendiente |

---

## Documentación Generada

- `docs/architecture/benchmark_f24.json` — métricas detalladas por etapa
- `docs/architecture/benchmark_f24_pipeline.json` — resumen del pipeline
- `docs/architecture/F24_CLOSEOUT.md` — este documento

---

## Preparación para F25 (Knowledge Fusion)

F24 deja preparado:

1. **`evidence_id`** estable en cada pieza de evidencia → F25 puede referirse
   a evidencia sin reindexar.
2. **`RankingScore`** descomponible → F25 puede inspeccionar contribuciones
   individuales sin recalcular.
3. **`content_hash`** y **`document_id`** en cada `Evidence` → F25 puede
   detectar cambios de contenido y URLs duplicadas.
4. **Resumen extractivo literal** → F25 puede operar sobre frases exactas
   sin alineamiento.
5. **Test E2E determinista** → detección inmediata de regresiones en F25.
