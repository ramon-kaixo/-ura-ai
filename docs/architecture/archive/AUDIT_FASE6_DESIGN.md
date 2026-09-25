# Auditoría Arquitectónica — Fase 6 (v0.2.0) — APROBADO

> **Fecha:** 2026-07-03
> **Documento auditado:** `FASE6_DESIGN.md` v0.2.0
> **Veredicto:** ✅ APROBADO CON OBSERVACIONES (todas corregidas)

---

## Cambios Aprobados vs v0.1.0

| # | Problema (v0.1.0) | Solución (v0.2.0) | Estado |
|---|---|---|---|
| 1 | **ISP violation**: `VectorBackend(Protocol)` forzaba `NotImplementedError` en Ollama y Qdrant | `Embedder(Protocol)` + `VectorStore(Protocol)` — cada clase implementa solo su Protocol. Zero `NotImplementedError`. | ✅ Corregido |
| 2 | **GraphRetriever coupling**: parámetro `vector_backend` en `retrieve_assets()` | `VectorAugmentedRetriever` wrapper independiente. `GraphRetriever` intacto. | ✅ Corregido |
| 3 | **Composite overengineering**: `CompositeVectorBackend` como workaround de #1 | Eliminado. Protocols separados + `VectorAugmentedRetriever` lo hacen innecesario. | ✅ Eliminado |
| 4 | **Gap de contenido**: `KnowledgeAsset` no tiene texto para embeddings | **Opción B** — `text_preview` es derivado, fuera del dominio. El suscriptor puentea desde `metadata["text_preview"]` a `VectorStore.upsert()`. | ✅ Cerrado |

## Decisiones Cerradas

| Decisión | Resolución |
|----------|------------|
| Composite | Eliminado |
| Cache | LRU in-process TTL 5min |
| Payload | Solo `asset_id`, `type`, `title`, `quality`, `extracted_at`, `text_preview[:500]` |
| Re-indexación | Script independiente `scripts/pro/reindex_vectors.py` |
| Vector size | Auto-detectado del primer embedding, fallback configurable 768 |
| Dependencia qdrant-client | Eliminada. HTTP directo con httpx. |

## Simplificaciones respecto a v0.1.0

- 4 clases + 4 archivos (antes 4 clases + 5 archivos incluyendo composite)
- Zero `NotImplementedError`
- Zero modificaciones a `GraphRetriever` o `AssetStore`
- Sin dependencia `qdrant-client`
- `upsert()` recibe tupla plana `(asset_id, vector, text_preview)`, no `KnowledgeAsset`

---

*Auditoría de diseño — Fase 6 v0.2.0 — 2026-07-03*
