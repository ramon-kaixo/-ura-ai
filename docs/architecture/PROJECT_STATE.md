# Knowledge Engine — Project State

> **Versión:** 0.7.0  
> **Fase actual:** 8 — Cerrada (todas completadas)  
> **Última actualización:** 2026-07-04  
> **Tests:** 471+ pasados — 0 nuevos fallos — 10 preexistentes (test_knowledge_engine: migration fixtures) — 4 error colección (test_openclaw, test_snc_anomalias, test_unit, test_vram_guard)  
> **Schema:** v14 (FTS5 op_assets/op_memory + op_lineage_edges + op_jobs.result_data)  
> **Determinismo:** sha256-v2  
> **API:** REST FastAPI :4097 — OpenAPI en `/docs`  
> **Últimas auditorías:** `PHASE7_CLOSEOUT.md` v3.0 — Fase 7 cerrada (H1 + 12 correcciones P0/P1 + 2 benchmark + 2 descartados). `PHASE6_CLOSEOUT.md` — Fase 6 cerrada. `CONTRACTS_FROZEN.md` — v2.0 (Fase 6+7). Fase 8 cerrada: 10 correcciones (cobertura tests + defensas + documentación).  

---

## Filosofía del proyecto

> **El conocimiento es el producto principal; la IA únicamente lo consume.**

El Knowledge Engine no es un LLM. No genera texto, no alucina, no «piensa».  
Su función es **almacenar, indexar, relacionar y recuperar conocimiento de forma determinista, auditable y reproducible.**

La IA (sea OpenAI, Ollama, Claude o cualquier otra) es un consumidor más del grafo. El motor no depende de ella. Puede funcionar sin LLM, sin embeddings y sin API externa.

Todo lo que el motor produce es verificable, repetible y trazable hasta su fuente original.

---

## Principios de diseño

| Principio | Significado |
|---|---|
| **Determinismo** | Mismo input → mismo output siempre. Sin IA en el pipeline crítico. |
| **Modularidad** | Cada componente tiene una responsabilidad única. `cli.py` no existe — es un paquete de 12 módulos. |
| **Compatibilidad** | Python 3.10+. Sin roturas de API pública. 175 tests perpetuos. |
| **Arquitectura hexagonal** | El dominio no conoce infraestructura. `Protocol` es la frontera. |
| **Domain-first** | `models.py` define el lenguaje. Todo lo demás lo implementa. |
| **Observabilidad** | Prometheus, logs estructurados, `correlation_id` de extremo a extremo. |
| **Seguridad por defecto** | Path traversal bloqueado, SSRF protegido, SafeEval con AST whitelist. |
| **Desacoplamiento** | EventBus, Protocol, Stores — ningún módulo llama a otro directamente salvo coordinación vía eventos. |

---

## Decisiones arquitectónicas (ADR)

| ADR | Decisión |
|---|---|
| [ADR-001](ADR-001-ndjson-audit.md) | NDJSON para auditoría del read path (lock-free) |
| [ADR-002](ADR-002-flock-compile-lock.md) | `flock(2)` para exclusión mutua del compile |
| [ADR-003](ADR-003-determinism-abi.md) | Determinism ABI v1 (sha256-v1 → v2) |
| [ADR-004](ADR-004-async-archive.md) | Archive asíncrono fire-and-forget |
| [ADR-005](ADR-005-sqlite-wal.md) | SQLite en modo WAL |
| [ADR-006](ADR-006-systemd-timer.md) | systemd timer como consumidor de `op_jobs` |
| [ADR-007](ADR-007-REGLA_NUCLEO.md) | Regla del núcleo con excepciones controladas |
| — | EventBus como backbone de Capa 11: sin llamadas directas entre módulos |
| — | Stores vía `Protocol`: SQLite es la implementación por defecto, no la única |
| — | `KnowledgeAsset` envuelve a `Document` sin modificarlo |

---

## Restricciones y prohibiciones

- ⚠️ **Núcleo modificable solo con ADR** (ver [ADR-007](ADR-007-REGLA_NUCLEO.md)). Extensiones backward-compatible permitidas (nuevos campos de config, topics de eventos, hooks). Refactor/renombrado prohibido.
- ❌ **No romper el determinismo.** Cualquier cambio que afecte al hash sha256-v2 requiere nueva versión mayor.
- ❌ **No añadir `sqlite3.connect()` fuera de `connection.py`.** El CI lo verifica.
- ❌ **No introducir dependencias circulares.** CI verifica que connection.py no importe de capas superiores.
- ❌ **No escribir en `kg_*` desde Capa 11.** Auditoría, metadatos, feedback, memory → solo `op_*`.
- ❌ **No hacer que la IA sea obligatoria.** GraphRAG funciona sin LLM.
- ✅ **SQLite es la implementación de referencia.** Neo4j, PostgreSQL, Qdrant son adaptadores futuros.
- ✅ **Los extractores deben ser `Protocol`s.** Cada tipo de activo (PDF, video, imagen) tiene su propio extractor.

---

## Arquitectura global

```
FUENTES                                         CAPA 11 (Metadatos Activos)
─────────                                       ───────────────────────────
                                                                               
  source/ (Markdown)                                                          
  PDFs, imágenes                                                              
  Vídeos, audio                                                               
  Repos Git                                                                    
  Web scraping                                                                 
  Conversaciones (Slack, API)                                                 
       │                                                                       
       ▼                                                                       
┌──────────────┐    ┌──────────────┐    ┌──────────────────────────────┐     
│  Scanner     │    │  Extractores  │    │     Knowledge Assets         │     
│  (existente) │───▶│  (Markdown,   │───▶│  Metadatos enriquecidos      │     
│              │    │   PDF, Video, │    │  AssetStore (SQLite)          │     
│              │    │   Audio, Git) │    │  MemoryStore (op_memory)      │     
└──────────────┘    └──────────────┘    │  LineageStore (op_lineage)    │     
                                        │  GovernanceStore (op_gov)     │     
                                        └──────────────┬───────────────┘     
                                                        │                    
                                                        ▼                    
┌────────────────────────────────────────────────────────────────────────┐   
│                   KNOWLEDGE GRAPH (virtual)                            │   
│                                                                         │   
│   Assets ───▶ Memory ───▶ Lineage ───▶ Governance                       │   
│         ╲        ╲          ╲          ╲                                │   
│          ╲        ╲          ╲          ╲                               │   
│           ╲        ╲          ╲          ╲                              │   
│            ▼        ▼          ▼          ▼                             │   
│         ┌──────────────────────────────────────────────────────┐       │   
│         │              GraphRetriever                          │       │   
│         │  retrieve_assets() → retrieve_memory()               │       │   
│         │  retrieve_neighbors() → retrieve_lineage()           │       │   
│         │  retrieve_governance() → build_context()             │       │   
│         └──────────────────────┬───────────────────────────────┘       │   
│                                │                                       │   
│                                ▼                                       │   
│         ┌──────────────────────────────────────────────────────┐       │   
│         │              ContextBuilder                          │       │   
│         │  Assets + Memory + Lineage + Governance + Neighbors  │       │   
│         │  → ContextBundle (determinista)                      │       │   
│         └──────────────────────┬───────────────────────────────┘       │   
│                                │                                       │   
│                                ▼                                       │   
│         ┌──────────────────────────────────────────────────────┐       │   
│         │              GraphRAG                                │       │   
│         │  ContextBundle → prompt contextualizado              │       │   
│         │  → LLM (Ollama, OpenAI, Claude, etc.)               │       │   
│         │    ↓                                                │       │   
│         │  Respuesta linkeada a los nodos del grafo           │       │   
│         └──────────────────────────────────────────────────────┘       │   
└────────────────────────────────────────────────────────────────────────┘   
```

---

## Inventario de componentes

### Núcleo (Fases 0–C, estable)

| Componente | Estado | LOC | Tests |
|---|---|---|---|
| `compiler.py` | ✅ Estable | 332 | — |
| `scanner.py` | ✅ Estable | 180 | — |
| `parser.py` | ✅ Estable | 157 | — |
| `reader.py` | ✅ Estable | 335 | — |
| `sqlite_writer.py` | ✅ Estable | 360 | — |
| `orchestrator.py` | ✅ Estable | 146 | — |
| `connection.py` | ✅ Estable | 76 | — |
| `eventbus.py` | ✅ Estable | 140 | — |
| `determinism.py` | ✅ v2 | 110 | — |
| `archiver.py` | ✅ Estable | 398 | — |
| `metrics.py` | ✅ Estable | 292 | — |

### CLI (12 módulos)

| Componente | Estado | LOC |
|---|---|---|
| `cli/main.py` | ✅ | 166 |
| `cli/compile.py` | ✅ | 95 |
| `cli/search.py` | ✅ | 69 |
| `cli/doctor.py` | ✅ | 54 |
| `cli/audit.py` | ✅ | 128 |
| `cli/archive.py` | ✅ | 48 |
| `cli/rules.py` | ✅ | 97 |
| `cli/pipeline.py` | ✅ | 22 |
| `cli/agent.py` | ✅ | 46 |
| `cli/api.py` | ✅ | 27 |
| `cli/notify.py` | ✅ | 18 |
| `cli/metadata.py` | ✅ | 106 |

### API REST

| Componente | Estado | Endpoints |
|---|---|---|
| `api.py` | ✅ | /health, /status, /compile, /search, /documents/{id}, /rules, /rules/eval, /archive, /feedback, /metrics, /metadata/lineage, /metadata/context, /metadata/retrieve, /memory… |

### Capa 11 (Metadatos Activos)

| Componente | Estado | LOC | Protocol |
|---|---|---|---|
| `ontology/` | ✅ Fase 0 | 380 | — |
| `extractors/markdown.py` | ✅ Fase 1 | 203 | `Extractor(Protocol)` |
| `extractors/base.py` | ✅ Fase 1 | 105 | `Extractor(Protocol)` + `ExtractorRegistry` |
| `extractors/pdf.py` | ✅ Fase 5 | 231 | `Extractor(Protocol)` |
| `extractors/image.py` | ✅ Fase 5 | 233 | `Extractor(Protocol)` |
| `extractors/office.py` | ✅ Fase 5 | 264 | `Extractor(Protocol)` |
| `extractors/audio.py` | ✅ Fase 5 | 206 | `Extractor(Protocol)` |
| `extractors/video.py` | ✅ Fase 5 | 294 | `Extractor(Protocol)` |
| `extractors/web.py` | ✅ Fase 5 | 326 | `Extractor(Protocol)` |
| `extractors/git.py` | ✅ Fase 5 | 294 | `Extractor(Protocol)` |
| `asset_store.py` | ✅ Fase 1 | 188 | `AssetStore(Protocol)` |
| `extraction_service.py` | ✅ Fase 1 | 114 | — |
| `lineage_store.py` | ✅ Fase 2 | 111 | `LineageStore(Protocol)` |
| `governance_store.py` | ✅ Fase 2 | 118 | `GovernanceStore(Protocol)` |
| `memory_store.py` | ✅ Fase 3 | 265 | `MemoryStore(Protocol)` |
| `graphrag.py` | ✅ Fase 4b | 320 | `GraphRetriever(Protocol)` |
| `connection_pool.py` | ✅ | 90 | — |
| `rollback.py` | ✅ | 150 | — |
| `snapshot_store.py` | ✅ | 76 | — |
| `vector_base.py` | ✅ Fase 6 | 97 | `Embedder(Protocol)`, `VectorStore(Protocol)`, `VectorItem`, `VectorResult` |
| `vector_ollama.py` | ✅ Fase 6 | 168 | `OllamaEmbedder` (implementa `Embedder`) |
| `vector_qdrant.py` | ✅ Fase 6 | 204 | `QdrantVectorStore` (implementa `VectorStore`) |
| `vector_retriever.py` | ✅ Fase 6 | 116 | `VectorAugmentedRetriever` |

### Pendientes de implementar

*(ninguno — todas las fases completadas)*

---

## Roadmap

### Completadas

```
Fase 0: Base              — scanner, parser, validator, writer, reader
Fase A: Archival          — git bundle, manifest, verify, restore
Fase B: Observabilidad    — metrics, structured logs, correlation_id
Fase C: Seguridad         — NDJSON audit, connection factory, path traversal fix
Fase D: Rules             — SafeEval, R001-R005
Fase E: Agentes           — Pipeline DAG, Agent framework
Fase F: API REST          — FastAPI, 10 endpoints, auth Bearer
Fase G: Feedback          — op_feedback_agg, ranking overlay
Fase H: Knowledge Base    — MkDocs generator
Fase J: Notify            — Webhook, Slack, Email, SSRF
Fase K: Producción        — _READER_POOL LRU, API body limit, compile timeout
Fase L: Chaos             — SIGTERM/KILL, WAL corrupt, disco lleno
  Capa 11:
    Fase 0: Ontology      — KnowledgeAsset, AssetType, Schema.org templates
    Fase 1: Extractores   — MarkdownExtractor, AssetStore, ExtractionService
    Fase 2: Lineage+Gov   — LineageStore, GovernanceStore, OpenLineage
    Fase 3: Memory        — MemoryStore, MemoryRecord, FTS op_memory
    Fase 4: GraphRAG      — GraphRetriever, ContextBuilder, ranking heurístico
    Fase 4b: Consol.      — retrieve_neighbors, cycle detection, tests, auditoría y cierre
    Fase 5: Extractores reales — PDF, Image, Office, Audio, Video, Web, Git — cerrada 2026-07-03
    Schema v13: Migración v12→v13 — content_sha256/wraps a columnas propias + op_memory — 2026-07-03
    Fase 6: Backend vectorial    — Embedder/VectorStore Protocols + OllamaEmbedder + QdrantVectorStore
                                  + VectorAugmentedRetriever + subscriber MetadataExtracted
                                  — 112 tests — Cerrada 2026-07-03
    Fase 7: Optimizaciones       — FTS5, edges, background queue, autorecuperación, reconcile,
                                    list_ids() Protocol — 6/6 benchmarks, 39 E2E checks,
                                    1 🔴 corregido (H1 loop infinito) + 12 correcciones P0/P1,
                                    16 corregidos + 9 backlog + 2 descartados — 461 tests passing
                                    — PHASE7_CLOSEOUT.md v3.0 — 2026-07-04
    Fase 8: Hardening + Docs     — Cobertura tests (B02-B04, B08), defensas (M04, M05),
                                    documentación (M02, M07-M09), 1 descartado (M06 — falso positivo)
                                    — 10 correcciones, 0 backlog remanente — 471+ tests pasados
                                    — 2026-07-04
```

### Pendientes

```

```

### Actual

```
Fase 7: Optimizaciones           — ✅ Cerrada (PHASE7_CLOSEOUT.md v3.0)
                                  Schema v14, 461 tests, 6/6 benchmarks
                                  1 🔴 + 12 P0/P1 + 3 benchmark = 16 corregidos, 9 backlog
Fase 8: Hardening + Docs         — ✅ Cerrada
                                  10 correcciones (B02-B04, B08, M02, M04, M05, M07-M09)
                                  1 descartado (M06 — falso positivo)
                                  0 backlog remanente. 471+ tests pasados.
```

---

## Riesgos abiertos

| Riesgo | Impacto | Probabilidad | Mitigación |
|---|---|---|---|---|---|
| `LIKE '%query%'` en title (1M+ assets) | Latencia >1s en búsquedas | Media | ✅ FTS5 implementado en Fase 7 (5.2× más rápido) |
| `get_lineage()` LIKE en arrays JSON | Latencia en queries de lineage | Media | ✅ `op_lineage_edges` implementado en Fase 7 |
| `retrieve_neighbors` N+1 queries | Limitado a depth=3 con branching bajo | Baja | Cache batch pendiente |
| Sin backend vectorial → ranking solo heurístico | Menor precisión en recuperación | Baja (diseño intencional) | ✅ Fase 6 añadió Embedder+VectorStore opcionales |
| Fuga de conexiones en feedback.py y agent.py | Conexiones colgadas en errores | Baja | Corregir en mantenimiento — mismo patrón que G02 |
| Extractores lentos (whisper, OCR) bloquean pipeline | Pipeline principal retrasado | Alta | ✅ Background queue implementada en Fase 7 |
| Dependencias externas no instaladas (ffmpeg, tesseract) | Extractores producen metadatos incompletos | Alta | ✅ Degradación graceful implementada en Fase 5 |
| SSRF en WebExtractor | Metadata cloud expuesta | 🔴 Crítico | ✅ Mitigado en Fase 5 — política SSRF completa, auditado |
| Decompression bomb en ImageExtractor | OOM en descompresión | 🔴 Alto | ✅ Mitigado en Fase 5 — MAX_IMAGE_PIXELS=100MP, validación previa |
| Threads zombis en timeout (S01) | Recursos no liberados tras timeout | 🟡 Medio | Documentado en PHASE5_CLOSEOUT.md |
| Thumbnails huérfanos (R02) | Acumulación de archivos garbage | 🟢 Bajo | Aceptado, pendiente de cleanup policy |
| GitExtractor sin MIME (A01) | No descubrible por `get_for_mime()` | 🟢 Bajo | Aceptado, invocación explícita requerida |

---

## Enlaces a documentación

| Documento | Propósito |
|---|---|
| `ADR-001-ndjson-audit.md` | NDJSON para auditoría |
| `ADR-002-flock-compile-lock.md` | flock para exclusión mutua |
| `ADR-003-determinism-abi.md` | Determinism ABI |
| `ADR-004-async-archive.md` | Archive asíncrono |
| `ADR-005-sqlite-wal.md` | WAL mode |
| `ADR-006-systemd-timer.md` | systemd timer |
| `ADR-007-REGLA_NUCLEO.md` | Regla del núcleo con excepciones controladas |
| `INVARIANTS.md` | 11 invariantes arquitectónicos |
| `API.md` | API pública congelada |
| `VERSIONING.md` | Política de versionado semántico |
| `RELEASE_CHECKLIST.md` | Checklist de liberación |
| `CAPA11_INTEGRATION.md` | Integración de Capa 11 con el núcleo |
| `CAPA11_AUDIT.md` | Auditoría técnica de Capa 11 |
| `PHASE4_CLOSEOUT.md` | Acta de cierre de Fase 4/4b |
| `PHASE5_CLOSEOUT.md` | Acta de cierre de Fase 5 — Extractores Reales |
| `PHASE6_CLOSEOUT.md` | Acta de cierre de Fase 6 — Backend Vectorial (nuevo) |
| `FASE5_DESIGN.md` | Diseño técnico de Fase 5 (v0.2.0) |
| `FASE6_DESIGN.md` | Diseño técnico de Fase 6 — Backend Vectorial (v0.3.0 ✅ Contratos congelados) |
| `AUDIT_FASE5_DESIGN.md` | Auditoría de diseño Fase 5 — SEC01/SEC02 corregidos |
| `AUDIT_FASE5_GLOBAL.md` | Auditoría global Fase 5 — 5 defectos corregidos, 2 documentados |
| `AUDIT_CONTRATOS_FASE6.md` | Auditoría de contratos públicos Fase 6 — 3 defectos bloqueantes corregidos |
| `AUDIT_CONTRATOS_FASE6_V2.md` | Auditoría de contratos v2 — pre-implementación |
| `CONTRACTS_FROZEN.md` | Interfaces congeladas de Fase 6+7+8 — Embedder, VectorStore, VectorAugmentedRetriever |
| `PREGUNTAS_INCOMODAS.md` | Análisis crítico post-Fase 5 — 10 preguntas incómodas |
| `AUDIT_PDFEXTRACTOR.md` | Auditoría PdfExtractor |
| `AUDIT_IMAGEEXTRACTOR.md` | Auditoría ImageExtractor |
| `EXTRACTOR_CHECKLIST.md` | Checklist obligatorio para extractores |
| `diagram.md` | Diagrama Mermaid de la arquitectura |
| `PROJECT_STATE.md` | **Este documento — punto de entrada único** |

---

*Mantenido manualmente. Actualizar al cerrar cada fase.*
