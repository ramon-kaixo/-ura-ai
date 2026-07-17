# Roadmap v2.0 — URA Architecture & Planning

**Versión:** v2.0.0-plan  
**Fecha:** 2026-07-17  
**Estado:** ✅ Plan Aprobado

---

## Resumen Ejecutivo

| Fase | Nombre | Bloques | Esfuerzo estimado | Prioridad |
|------|--------|---------|-------------------|-----------|
| F24 | Web Intelligence | 9 | Alto | 🥇 |
| F25 | Knowledge Fusion | 9 | Alto | 🥇 |
| F26 | Memoria Histórica | 9 | Alto | 🥇 |
| F27 | Agentes Autónomos | 9 | Muy Alto | 🥈 |

**Total:** 36 bloques atómicos  
**Dependencias:** F24 → F25 → F26 → F27 (estrictas)  
**API pública congelada:** `motor.core.llm` y `motor.core.evaluation` no se modifican.

---

# F24 — Web Intelligence

## Objetivo

Dotar a URA de la capacidad de buscar, extraer, procesar y sintetizar información de la web con citas y trazabilidad.

## ADR-024-01: Web Intelligence como pipeline de plugins

**Estado:** Aprobado  
**Contexto:** Necesitamos un sistema extensible de búsqueda y extracción web sin acoplar proveedores concretos.  
**Decisión:** Cada buscador, crawler y extractor será un plugin independiente registrable en un Registry específico.  
**Consecuencias:** + extensibilidad, − rendimiento comparado con integración directa.

## Arquitectura

```
motor/web/
├── __init__.py
├── registry.py          — WebProviderRegistry (buscadores, crawlers, extractores)
├── models.py            — WebResult, WebDocument, Citation
├── searcher/
│   ├── __init__.py
│   ├── base.py          — BaseSearcher (ABC)
│   └── providers/
│       ├── duckduckgo.py
│       └── searxng.py
├── crawler/
│   ├── __init__.py
│   ├── base.py          — BaseCrawler (ABC)
│   └── providers/
│       ├── httpx.py
│       └── playwright.py (opcional)
├── extractor/
│   ├── __init__.py
│   ├── base.py          — BaseExtractor (ABC)
│   └── providers/
│       ├── readability.py
│       ├── markdown.py
│       └── llm.py       — Extracción vía LLM
├── cleaner/
│   ├── __init__.py
│   ├── dedup.py         — Deduplicación por similitud
│   └── quality.py       — Filtros de calidad
├── ranker/
│   ├── __init__.py
│   └── ranker.py        — Ranking por relevancia + frescura
├── summarizer/
│   ├── __init__.py
│   └── summarizer.py    — Resumen multi-fuente vía LLM
├── citation/
│   ├── __init__.py
│   └── citation.py      — Generación de citas con trazabilidad
├── pipeline.py          — WebPipeline (orquesta todo el flujo)
└── config.py            — Configuración del módulo web

scripts/pro/
└── benchmark_web.py     — Benchmark de búsqueda y extracción
```

## Componentes Nuevos

| Componente | Propósito | Dependencias |
|------------|-----------|--------------|
| `BaseSearcher` | ABC para buscadores (search → URLs) | httpx |
| `BaseCrawler` | ABC para crawlers (URL → HTML) | httpx |
| `BaseExtractor` | ABC para extractores (HTML → texto estructurado) | — |
| `WebPipeline` | Orquestador del pipeline completo | Todos los anteriores |
| `Citation` | Generación de citas con URL, fecha, fragmento | — |

## Componentes Reutilizados

| Componente | Fase | Uso en F24 |
|------------|------|------------|
| `LLMRouter` | F18 | Summarizer, extractor LLM |
| `BaseLLMProvider` | F18 | Extracción y resumen vía LLM |
| `PerformanceBaseline` | F20 | Benchmarks de latencia por buscador |
| `EvaluationEngine` | F21 | Evaluación de calidad de resultados |
| `motor.core.secrets` | F17.5 | API keys de buscadores |

## API Pública

```python
from motor.web import WebPipeline
from motor.web.models import WebResult, WebDocument, Citation

# Pipeline principal
pipeline = WebPipeline()
results = pipeline.search("query", sources=["duckduckgo", "searxng"])
# → list[WebResult] con título, URL, snippet, score

document = pipeline.fetch(url)
# → WebDocument con contenido, metadatos, readability score

summary = pipeline.summarize(query, results)
# → dict con summary, citations: list[Citation]

# Registro de proveedores
from motor.web.searcher.base import BaseSearcher
pipeline.register_searcher("custom", MySearcher())
```

## Contratos

### BaseSearcher

```python
class BaseSearcher(ABC):
    @abstractmethod
    def search(self, query: str, limit: int = 10) -> list[WebResult]: ...
    @property
    def name(self) -> str: ...
```

### BaseCrawler

```python
class BaseCrawler(ABC):
    @abstractmethod
    def fetch(self, url: str, timeout: int = 30) -> str: ...
    @property
    def name(self) -> str: ...
```

### BaseExtractor

```python
class BaseExtractor(ABC):
    @abstractmethod
    def extract(self, html: str, url: str) -> WebDocument: ...
    @abstractmethod
    def extract_text(self, html: str) -> str: ...
```

## Riesgos

| Riesgo | Impacto | Mitigación |
|--------|---------|------------|
| Bloqueo por rate limiting | Medio | Backoff + rotación de proxies |
| Contenido dinámico (JS) | Medio | Crawler Playwright opcional |
| Calidad variable de fuentes | Medio | Filtros de calidad + ranking |
| Legal (robots.txt, ToS) | Alto | Cache de robots.txt + modo legal |
| Dependencia de DuckDuckGo/SearXNG | Medio | Registry extensible |

## Dependencias Nuevas

| Dependencia | Justificación | Alternativa |
|-------------|---------------|-------------|
| `readability-lxml` | Extracción de contenido principal | `trafilatura` (más ligero) |
| `lxml` | Parseo HTML rápido | `html.parser` (lento) |

> Nota: `httpx` ya está disponible. `playwright` es opcional (solo para crawler JS).

## Orden de Bloques

```
B1 Arquitectura (documentación + ADR)
B2 Buscadores (DuckDuckGo, SearXNG)
B3 Crawlers (httpx, playwright opcional)
B4 Extracción (readability, LLM)
B5 Limpieza y deduplicación
B6 Ranking
B7 Resumen (LLM multi-fuente)
B8 Citas y trazabilidad
B9 Benchmark y cierre
```

## Criterios de Aceptación

1. ✅ Búsqueda en ≥2 fuentes
2. ✅ Extracción de contenido con y sin LLM
3. ✅ Resumen multi-fuente con citas
4. ✅ Trazabilidad (cada afirmación → URL)
5. ✅ Benchmark de latencia y calidad
6. ✅ 0 regresiones en tests existentes

## Benchmark Esperado

| Operación | Target | Límite |
|-----------|--------|--------|
| Búsqueda | < 2s | 5s |
| Crawling | < 3s | 10s |
| Extracción | < 1s | 3s |
| Resumen (LLM) | < 5s | 15s |
| Pipeline completo | < 10s | 30s |

## Tests Necesarios

- test_searcher_base, test_searcher_duckduckgo
- test_crawler_base, test_crawler_httpx
- test_extractor_readability, test_extractor_llm
- test_cleaner_dedup, test_cleaner_quality
- test_ranker, test_summarizer, test_citation
- test_pipeline_completo, test_json_export
- test_thread_safe, test_router_independence

---

# F25 — Knowledge Fusion

## Objetivo

Fusionar múltiples fuentes de información en un modelo de conocimiento coherente, resolviendo conflictos y manteniendo versionado.

## ADR-025-01: Fusión como capa sobre KE

**Estado:** Aprobado  
**Contexto:** El Knowledge Engine (KE) ya almacena documentos fragmentados. Necesitamos una capa que fusione fuentes con conflictos.  
**Decisión:** La fusión opera sobre el KE existente sin modificar su esquema. Los conflictos se resuelven por mayoría ponderada + frescura.  
**Consecuencias:** + separación de concerns, − rendimiento en escritura.

## Arquitectura

```
motor/knowledge/
├── __init__.py
├── models.py            — KnowledgeItem, Source, Conflict, Resolution
├── fusion/
│   ├── __init__.py
│   ├── engine.py        — FusionEngine (orquestador)
│   ├── resolver.py      — ConflictResolver (mayoría, frescura, confianza)
│   └── merger.py        — SourceMerger (fusión de campos)
├── versioning/
│   ├── __init__.py
│   ├── store.py         — VersionStore (historial de cambios)
│   └── diff.py          — Differ (diff entre versiones)
├── incremental/
│   ├── __init__.py
│   └── updater.py       — IncrementalUpdater (actualización parcial)
├── integration/
│   ├── __init__.py
│   └── ke_bridge.py     — Bridge con Knowledge Engine existente
├── config.py
└── evaluation/
    ├── __init__.py
    └── evaluator.py     — Evaluación de calidad de fusión
```

## Componentes Reutilizados

| Componente | Fase |
|------------|------|
| `EvaluationEngine` | F21 |
| `PerformanceBaseline` | F20 |
| `LLMRouter` | F18 |
| `motor.core.secrets` | F17.5 |

## API Pública

```python
from motor.knowledge import FusionEngine

engine = FusionEngine()
item = engine.fuse(sources=[
    {"text": "...", "source": "web", "confidence": 0.9},
    {"text": "...", "source": "pdf", "confidence": 0.7},
])
# → KnowledgeItem con texto fusionado, conflictos resueltos, fuentes

engine.resolve_conflicts(item)
# → ConflictResolution con decisión, justificación

version = engine.save_version(item)
# → Version con timestamp, diff, hash
```

## Orden de Bloques

```
B1 Arquitectura
B2 Modelo de conocimiento
B3 Resolución de conflictos
B4 Fusión de fuentes
B5 Actualización incremental
B6 Versionado
B7 Integración con KE
B8 Evaluación
B9 Benchmark y cierre
```

---

# F26 — Memoria Histórica y Aprendizaje Continuo

## Objetivo

Dotar a URA de memoria persistente: conversacional, de proyectos y de preferencias del usuario, con aprendizaje continuo del KE.

## ADR-026-01: Memoria como capa separada del KE

**Estado:** Aprobado  
**Contexto:** El KE almacena conocimiento factual. La memoria debe almacenar contexto episódico, preferencias y evolución de proyectos.  
**Decisión:** Sistema de memoria independiente que alimenta al KE pero no se mezcla con él.  
**Consecuencias:** + claridad arquitectónica, − necesidad de sincronización.

## Arquitectura

```
motor/memory/
├── __init__.py
├── models.py            — MemoryItem, Conversation, Project, Preference
├── conversational/
│   ├── __init__.py
│   ├── store.py         — ConversationalMemory (últimas N interacciones)
│   └── summarizer.py    — Resumen de conversaciones largas
├── project/
│   ├── __init__.py
│   └── store.py         — ProjectMemory (estado, decisiones, contexto)
├── preference/
│   ├── __init__.py
│   └── learner.py       — PreferenceLearner (implícito + explícito)
├── continuous/
│   ├── __init__.py
│   ├── learner.py       — ContinuousLearner (reindexación automática)
│   └── scheduler.py     — Programación de ciclos de aprendizaje
├── integration/
│   ├── __init__.py
│   └── ke_updater.py    — Actualización automática del KE
├── config.py
└── evaluation/
    ├── __init__.py
    └── evaluator.py     — Evaluación de calidad de memoria
```

## Orden de Bloques

```
B1 Arquitectura
B2 Memoria conversacional
B3 Memoria de proyectos
B4 Aprendizaje de preferencias
B5 Actualización automática del KE
B6 Reindexación
B7 Aprendizaje continuo
B8 Evaluación
B9 Benchmark y cierre
```

---

# F27 — Agentes Autónomos

## Objetivo

Crear un sistema de agentes autónomos con planificación, ejecución, herramientas, coordinación multi-agente y supervisión humana.

## ADR-027-01: Agentes como pipelines ejecutables

**Estado:** Aprobado  
**Contexto:** Necesitamos agentes que puedan planificar, ejecutar tareas, usar herramientas y coordinarse entre sí.  
**Decisión:** Cada agente es un pipeline ejecutable con planner, executor, tool manager y recuperación.  
**Consecuencias:** + complejidad, + flexibilidad máxima.

## Arquitectura

```
motor/agents/
├── __init__.py
├── models.py            — Task, Plan, Step, AgentResult, Tool
├── planner/
│   ├── __init__.py
│   └── planner.py       — Planner (descompone objetivos en pasos)
├── executor/
│   ├── __init__.py
│   └── executor.py      — Executor (ejecuta pasos del plan)
├── tools/
│   ├── __init__.py
│   ├── registry.py      — ToolRegistry
│   ├── base.py          — BaseTool (ABC)
│   └── providers/
│       ├── web_search.py
│       ├── web_fetch.py
│       ├── code_exec.py
│       ├── file_ops.py
│       └── llm_call.py
├── multiagent/
│   ├── __init__.py
│   ├── orchestrator.py  — MultiAgentOrchestrator
│   └── coordinator.py   — Coordinator (asigna tareas, consolida)
├── recovery/
│   ├── __init__.py
│   └── recovery.py      — ErrorRecovery (retry, replan, escalate)
├── human/
│   ├── __init__.py
│   └── interface.py     — HumanInTheLoop (aprobación, feedback)
├── config.py
└── evaluation/
    ├── __init__.py
    └── evaluator.py     — Evaluación de calidad de agentes
```

## Orden de Bloques

```
B1 Arquitectura
B2 Planner
B3 Executor
B4 Tool Manager
B5 Multiagente
B6 Coordinación
B7 Recuperación ante errores
B8 Human-in-the-loop
B9 Benchmark y cierre
```

---

# Plan de Ejecución por Bloque

A continuación, cada bloque atómico con sus archivos, restricciones y validaciones.

---

## F24-B1 — Web Intelligence Architecture

**Objetivo:** Crear la estructura del módulo web y los contratos base.
**Archivos a crear:**
- `motor/web/__init__.py`
- `motor/web/registry.py`
- `motor/web/models.py`
- `motor/web/searcher/base.py`
- `motor/web/searcher/__init__.py`
- `motor/web/crawler/base.py`
- `motor/web/crawler/__init__.py`
- `motor/web/extractor/base.py`
- `motor/web/extractor/__init__.py`
- `docs/architecture/FASE24_PROPOSAL.md` (ADR + arquitectura)
**Archivos a modificar:** Ninguno
**Restricciones:** No modificar API pública existente. No añadir dependencias externas en B1.
**Validaciones:** py_compile, ruff, pytest completo
**Commit sugerido:** `feat(f24): add web intelligence architecture`
**Tag esperado:** `v0.24.0-b1`

---

## F24-B2 — Searchers (DuckDuckGo, SearXNG)

**Objetivo:** Implementar buscadores.
**Archivos a crear:**
- `motor/web/searcher/providers/__init__.py`
- `motor/web/searcher/providers/duckduckgo.py`
- `motor/web/searcher/providers/searxng.py`
- `motor/tests/test_searcher.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** httpx para HTTP. Sin dependencias nuevas.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add web searchers (duckduckgo, searxng)`

---

## F24-B3 — Crawlers

**Objetivo:** Implementar crawlers para fetch de URLs.
**Archivos a crear:**
- `motor/web/crawler/providers/__init__.py`
- `motor/web/crawler/providers/httpx_crawler.py`
- `motor/tests/test_crawler.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** httpx base. Playwright opcional (no incluido en B3).
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add web crawlers`

---

## F24-B4 — Extractors (Readability, LLM)

**Objetivo:** Implementar extractores de contenido.
**Archivos a crear:**
- `motor/web/extractor/providers/__init__.py`
- `motor/web/extractor/providers/readability.py`
- `motor/web/extractor/providers/llm_extractor.py`
- `motor/tests/test_extractor.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** readability-lxml es dependencia externa justificada. LLM usa motor.core.llm.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add content extractors`

---

## F24-B5 — Cleaner & Dedup

**Objetivo:** Implementar limpieza y deduplicación.
**Archivos a crear:**
- `motor/web/cleaner/__init__.py`
- `motor/web/cleaner/dedup.py`
- `motor/web/cleaner/quality.py`
- `motor/tests/test_cleaner.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** Sin dependencias nuevas. Usar stdlib + sklearn opcional.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add document cleaner and deduplication`

---

## F24-B6 — Ranking

**Objetivo:** Implementar ranking de resultados.
**Archivos a crear:**
- `motor/web/ranker/__init__.py`
- `motor/web/ranker/ranker.py`
- `motor/tests/test_ranker.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** Ranking por relevancia, frescura, dominio. Sin ML.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add result ranking`

---

## F24-B7 — Summarizer

**Objetivo:** Implementar resumen multi-fuente vía LLM.
**Archivos a crear:**
- `motor/web/summarizer/__init__.py`
- `motor/web/summarizer/summarizer.py`
- `motor/tests/test_summarizer.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** Usar LLMRouter para generación. Sin prompts hardcodeados.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add multi-source summarizer`

---

## F24-B8 — Citations & Traceability

**Objetivo:** Implementar sistema de citas con trazabilidad.
**Archivos a crear:**
- `motor/web/citation/__init__.py`
- `motor/web/citation/citation.py`
- `motor/tests/test_citation.py`
**Archivos a modificar:** `motor/web/__init__.py`
**Restricciones:** Cada cita debe contener URL, fragmento, timestamp.
**Validaciones:** py_compile, ruff, pytest
**Commit sugerido:** `feat(f24): add citation system with traceability`

---

## F24-B9 — Benchmark & Closeout

**Objetivo:** Benchmark de Web Intelligence y cierre de F24.
**Archivos a crear:**
- `scripts/pro/benchmark_web.py`
- `docs/architecture/FASE24_CLOSEOUT.md`
**Archivos a modificar:** Ninguno
**Restricciones:** Benchmark debe medir búsqueda, crawl, extracción, resumen.
**Validaciones:** py_compile, ruff, pytest, benchmark, tag
**Commit sugerido:** `docs(f24): publish web intelligence closeout`
**Tag esperado:** `v0.24.0-fase24`

---

## F25 a F27 — Estructura de Bloques

La estructura de F25, F26 y F27 sigue el mismo patrón que F24:

- **B1:** Arquitectura → Archivo de propuesta + ADR + módulos base
- **B2–B7:** Implementación incremental de cada subsistema
- **B8:** Evaluación del subsistema
- **B9:** Benchmark + closeout + tag

Las especificaciones detalladas (archivos, restricciones, commits) para F25–F27 se generarán al inicio de cada fase, siguiendo la arquitectura descrita en este documento.

---

# Estrategia de Migración

| Desde | Hacia | Mecanismo |
|-------|-------|-----------|
| F18 API pública | F24–F27 | Sin cambios — solo se añaden nuevos módulos |
| KE existente | F25 Fusion | Bridge sin modificar KE |
| F18 Router | F24–F27 | Reutilizado para LLM calls |
| F20 Baseline | F24–F27 | Reutilizado para benchmarks |
| F21 Evaluation | F25–F26 | Reutilizado para evaluaciones |

**Regla de Oro:** Ninguna fase futura puede modificar archivos existentes en `motor/core/llm/` o `motor/core/evaluation/`. Solo se añaden nuevos módulos en `motor/web/`, `motor/knowledge/`, `motor/memory/`, `motor/agents/`.

# Tags Esperados

```
v0.24.0-fase24    — Web Intelligence
v0.25.0-fase25    — Knowledge Fusion
v0.26.0-fase26    — Memoria Histórica
v0.27.0-fase27    — Agentes Autónomos
v2.0.0            — Versión 2.0 Estable
```
