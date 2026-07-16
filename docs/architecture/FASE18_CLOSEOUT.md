# Fase 18 — Closeout: Cliente Multiproveedor

**Versión:** v0.18.0-fase18  
**Fecha:** 2026-07-16  
**Estado:** ✅ Cerrada

## Resumen por Bloque

| Bloque | Archivos | Estado |
|--------|----------|--------|
| B1 — Auditoría | `docs/architecture/F18_CONSUMERS.md` | ✅ Completado |
| B2 — Contrato | `motor/core/llm/base.py`, `motor/core/llm/__init__.py`, `motor/core/llm/ollama.py` | ✅ Completado |
| B3 — Registry | `motor/core/llm/registry.py` | ✅ Completado |
| B4 — Router | `motor/core/llm/router.py` | ✅ Completado |
| B5 — OpenAI | `motor/core/llm/openai.py` | ✅ Completado |
| B6 — Configuración | `config.local.json`, `motor/core/llm/__init__.py` | ✅ Completado |
| B7 — Golden Tests | `motor/tests/test_llm_providers.py` | ✅ Completado |
| B8 — Benchmarks | `scripts/pro/benchmark_llm.py` | ✅ Completado |
| B9 — Validación Final | `docs/architecture/FASE18_CLOSEOUT.md` | ✅ Completado |

## Archivos Modificados/Creados

### Creados
- `motor/core/llm/base.py` — `BaseLLMProvider` (ABC: generate, embed, embed_async, health)
- `motor/core/llm/openai.py` — `OpenAIProvider(BaseLLMProvider)`
- `motor/core/llm/registry.py` — `ProviderRegistry` (register, get, unregister, list, default)
- `motor/core/llm/router.py` — `LLMRouter` (selección por tarea, fallback, delegación)
- `motor/tests/test_llm_providers.py` — 26 golden tests
- `docs/architecture/F18_CONSUMERS.md` — Auditoría de consumidores

### Modificados
- `motor/core/llm/__init__.py` — Read CONFIG para seleccionar proveedor; pobla Registry
- `motor/core/llm/ollama.py` — Refactorizado a `OllamaProvider(BaseLLMProvider)`
- `scripts/pro/benchmark_llm.py` — `--provider` flag, router integration
- `config.local.json` — Sección `llm.providers.openai.*`
- `pyproject.toml` — `per-file-ignores` para `motor/tests/*`

## Métricas de Validación

| Check | Resultado |
|-------|-----------|
| `py_compile` (8 módulos) | ✅ 0 errores |
| `ruff` (módulos nuevos/tocados) | ✅ 0 errores nuevos |
| `ruff` (benchmark_llm, pre-existing) | ✅ 1 error pre-existente (EXE001) |
| `pytest motor/tests/` | ✅ 38/38 passed (26 golden + 12 pre-existing) |
| `pytest` (full suite pre-existing failures) | ⚠️ 3 collection errors (pre-existing, no regresiones) |
| `audit_config.py` | ✅ 0 problemas |
| `audit_secrets.py` (F18 files) | ✅ 0 reales (2 falsos positivos en openai.py) |
| `benchmark_llm --iterations 1` | ✅ generación + embeddings OK |
| API pública `motor.core.llm` | ✅ Congelada, 8 consumidores compatibles |

## Incidencias

| ID | Severidad | Descripción | Estado |
|----|-----------|-------------|--------|
| I01 | Baja | `system_config.json` tiene `chattr +i` (F14-F01). No se pudo añadir sección `llm`. Workaround: `config.local.json`. Resolver en F23. | Abierto |
| I02 | Informativa | `audit_secrets.py` levanta 2 falsos positivos en `openai.py:50` (nombres de configuración, no secretos). | Cerrado (falso positivo) |
| I03 | Informativa | Los 8 consumidores existentes no requieren cambios para F18 (ver B1). | Cerrado |

## Riesgos

- **Selección de proveedor por CONFIG**: si `config.local.json` se elimina en F23 sin migrar `llm.*` a `system_config.json`, el sistema perderá la capacidad de seleccionar proveedor mediante configuración. La sección `llm` debe añadirse a `system_config.json` antes de F23.
- **OpenAIProvider sin API key**: el código falla gracefulmente (devuelve errores tipo "connection error"). No hay validación temprana de `OPENAI_API_KEY`.
- **system_config.json inmutable**: bloquea cualquier modificación del archivo. Workaround activo vía `config.local.json`.

## Decisión

**GO ✅** — Fase 18 lista para tag. Criterios de aceptación cumplidos:

1. ✅ API pública de `motor.core.llm` intacta
2. ✅ Ningún consumidor modificado para soportar OpenAI
3. ✅ Registry operativo
4. ✅ Router operativo
5. ✅ OpenAI implementado
6. ✅ Ollama funciona exactamente igual
7. ✅ Golden tests completos (26 tests)
8. ✅ Benchmarks por proveedor
9. ✅ py_compile OK
10. ✅ ruff sin errores nuevos
11. ✅ pytest sin regresiones (pre-existing failures unchanged)
12. ✅ Documentación actualizada

## Tag

```bash
git tag -a v0.18.0-fase18 -m "F18 — Cliente Multiproveedor"
```

## Próximos Pasos (F19+)

- Migrar `llm.*` de `config.local.json` a `system_config.json` (requiere resolver `chattr +i`)
- Añadir validación temprana de `OPENAI_API_KEY`
- Soporte para proveedores adicionales (Groq, DeepSeek, etc.)
- Caché distribuida de embeddings entre proveedores
