# Auditoría de Mocks Internos — Fase 2 (deuda técnica)

## Hallazgo 2026-08-01

Los siguientes tests mockean métodos/funciones internas del propio proyecto,
violando la regla #8 (mock en fronteras externas, no en lógica propia).

| Archivo de test | Método mockeado | Archivo real | Severidad | Notas |
|-----------------|-----------------|--------------|-----------|-------|
| `test_qdrant_client.py` | `_conectar` | `motor/core/qdrant_client.py` | 🔴 Alta | Método privado de conexión |
| `test_qdrant_client.py` | `DegradedMode` | `motor/core/qdrant_client.py` | 🔴 Alta | Clase interna |
| `test_qdrant_client.py` | `generar_embedding_async` | `motor/core/qdrant_client.py` | 🔴 Alta | Lógica de negocio |
| `test_qdrant_client.py` | `llm_embed` | `motor/core/qdrant_client.py` | 🔴 Alta | Embedding real |
| `test_ura_qdrant.py` | `_conectar` | `motor/core/qdrant_client.py` | 🔴 Alta | Duplicado del anterior |
| `test_ura_qdrant.py` | `generar_embeddings_batch` | `motor/core/qdrant_client.py` | 🔴 Alta | Lógica de negocio |
| `test_ura_qdrant.py` | `buscar_por_similitud` | `motor/core/qdrant_client.py` | 🔴 Alta | Lógica de negocio |
| `test_ura_qdrant.py` | `generar_embedding` | `motor/core/qdrant_client.py` | 🔴 Alta | Lógica de negocio |
| `test_vector_ollama.py` | `_embed` | `knowledge/engine/vector_ollama.py` | 🟡 Media | Función privada |
| `test_vector_ollama.py` | `_health` | `knowledge/engine/vector_ollama.py` | 🟡 Media | Función privada |
| `test_fase7.py` | `vector_ollama._health` | `knowledge/engine/vector_ollama.py` | 🟡 Media | Duplicado |
| `test_vector_subscriber.py` | `SQLiteAssetStore` | `knowledge/engine/asset_store.py` | 🟡 Media | Clase de repositorio |

## Impacto

- **Cobertura mentirosa**: estos tests reportan % alto en `qdrant_client.py` pero no ejecutan la lógica real.
- **Regresión oculta**: un cambio en `_conectar` o `generar_embedding` no se detecta porque está mockeado.
- **Falso positivo de calidad**: el dashboard dice "95% cobertura" pero el 60% es mocks.

## Plan de corrección (Fase 6 — post-refactor)

1. Extraer la lógica de conexión Qdrant a un adapter externo (`infra/qdrant_adapter.py`).
2. Testear el adapter con Qdrant real en Docker (integración) o con `responses` (HTTP mock).
3. Testear `qdrant_client.py` con el adapter inyectado (sin mock de métodos privados).
4. Para `vector_ollama`: testear con Ollama real en CI (Docker) o usar `responses` para el endpoint HTTP.
5. Para `SQLiteAssetStore`: usar SQLite real en memoria (ya lo hacemos en otros tests).

## Estado

- **Detectado**: 2026-08-01
- **Prioridad**: P2 (no bloquea Fase 4/5, pero invalida métricas de cobertura)
- **Responsable**: Post-Fase 5

## Flaky Tests Detectados (2026-08-01)

| Archivo | Test | Modo | Resultado |
|---------|------|------|-----------|
| `test_router_handler.py` | `test_post_context_critical_logged` | Solo (individual) | ✅ Pasa |
| `test_router_handler.py` | `test_post_context_critical_logged` | Suite completa | ❌ Falla (9 tests) |
| `test_router_handler.py` | Todo el archivo | Solo | ✅ 25/25 |
| `test_router_handler.py` | Todo el archivo | Suite completa | ✅ 25/25 |

**Diagnóstico:** Estado compartido en `sys.modules` entre tests. Otros tests modifican `core.model_router.metrics` o `core.model_router.proxy` y el monkeypatch de `_patch_metrics` no se aplica correctamente cuando el módulo ya está cacheado con otra referencia.

**Impacto:** Bajo — la suite CI pasa al 100%. Solo falla en ejecución parcial con cierto orden.

**Fix propuesto (Fase 6):** Refactorizar `_patch_metrics` para usar `monkeypatch.setattr("core.model_router.handler.metrics", fake)` en lugar de parchear `sys.modules` directamente.
