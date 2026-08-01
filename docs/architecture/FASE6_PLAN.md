# Plan Fase 6 — Post-Merge (cuando OpenCode termine Fase 5)

## Estado bloqueante (resuelto tras merge de `refactor/model-router-package`)

| Archivo | Bloqueo | Tests pendientes |
|---------|---------|------------------|
| scripts/pro/reindex_vectors.py | Importa knowledge.engine.* | 3-4 (dry-run, db missing, batch size) |
| scripts/pro/uitars_hetzner.py | Importa motor.core.secrets | 2-3 (VNC mock, screenshot, error path) |
| scripts/pro/test_latencia_mac.py | Importa core.voice.* | 2-3 (pipeline init, device none, latency) |
| scripts/pro/router_rate_limiter.py | Importa motor.* | 3-4 (rate limit, burst, reset) |
| scripts/pro/backup_f26_memory.py | Importa motor.memory | 2 (backup, restore) |
| scripts/pro/cleanup_assistant.py | Importa motor.assistant.* | 2 (cleanup, empty) |
| scripts/pro/ura-query.py | Importa core.memory_engine | 3-4 (query, sources, json output) |
| scripts/pro/knowledge_engine.py | Thin wrapper | Ya cubierto via cli tests |
| scripts/pro/patch_timestamps.py | One-off migracion | No testear |
| scripts/pro/captura_virtual.py | Necesita X11 | Integracion con Docker |

## Deuda tecnica documentada (TEST_AUDIT_MOCKS.md)

### Mocks internos (12 hallazgos)
- test_qdrant_client.py: _conectar, DegradedMode, generar_embedding_async, llm_embed
- test_ura_qdrant.py: _conectar, generar_embeddings_batch, buscar_por_similitud, generar_embedding
- test_vector_ollama.py: _embed, _health
- test_fase7.py: vector_ollama._health
- test_vector_subscriber.py: SQLiteAssetStore

### Flaky tests (1 hallazgo)
- test_router_handler.py: 9 tests fallan en ejecucion parcial (sys.modules compartido)

## Orden de ejecucion Fase 6

1. Merge de `refactor/model-router-package` → resolver conflictos en 4 archivos de test
2. Arreglar mocks internos: extraer adapters, testear con infra real (Docker)
3. Arreglar flaky tests: refactorizar _patch_metrics para no usar sys.modules
4. Testear scripts/ restantes (9 archivos, ~25 tests)
5. Verificacion final: suite completa verde + cobertura >= 45%

## Estimacion
- Merge + conflictos: 10 min
- Mocks internos: 2-3 sesiones (complejo)
- Flaky tests: 30 min
- Scripts restantes: 1 sesion
- Total: ~4-5 horas de trabajo efectivo
