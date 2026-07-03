# ADR-003: Determinism ABI v1

**Fecha:** 2026-07-01
**Estado:** Aceptado

## Contexto
El determinism hash debe ser reproducible entre máquinas, versiones de Python, sistemas operativos y configuraciones regionales.

## Decisión
Algoritmo `sha256-v1`:
- SHA-256 de `json.dumps({"nodes": [...], "edges": [...]}, sort_keys=True)`
- Columnas incluidas: `id, type, path, content_sha256, body, frontmatter, quality, confidence, embed_hash` de kg_nodes
- Columnas excluidas: `updated_at, semantic, metadata`
- ORDER BY explícito: `kg_nodes.id`, `kg_edges.src, dst, relation`
- Sin timestamps, sin rowid, sin locale-dependent formatting

## Consecuencias
- El hash es función pura del contenido semántico.
- `determinism_algorithm` versiona el ABI ("sha256-v1").
- Un cambio futuro requiere nuevo algoritmo + migración.
