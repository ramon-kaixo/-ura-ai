# Changelog v1.0.0-rc

**Fecha:** 2026-07-16  
**Estado:** Release Candidate

## Resumen Ejecutivo

Release Candidate del sistema multi-agente URA con cliente LLM unificado,
7 proveedores, resiliencia, observabilidad, profiling continuo y evaluación
de Retrieval. 398 tests funcionales, API pública congelada.

## F15 — F23: Cambios desde v0.14.x

### F15 — Migración HTTP (Ollama)
Migración de llamadas HTTP directas a `generate()` + `health()` del motor.
`debate_engine.py` y `ura_multi_agent.py` migrados. 0 HTTP directo a Ollama
en `core/`, `motor/`, `knowledge/`.

### F16 — Empaquetado y Deuda
Eliminación de dependencias rotas (`import httpx`), tests actualizados.

### F17 — Configuración Unificada
`UraConfig` como vista tipada de `CONFIG`. Deprecación de `config.local.json`.
Corrección de `get_ollama_urls()`. Auditoría automática vía `audit_config.py`.

### F17.5 — Gestión de Secretos
`motor/core/secrets.py` con backends: env → `/etc/ura/secrets.env` → default.
15 consumidores migrados. Auditoría automática vía `audit_secrets.py`.

### F18 — Cliente Multiproveedor
- `BaseLLMProvider` (ABC): generate, embed, embed_async, health
- `OllamaProvider`, `OpenAIProvider`
- `ProviderRegistry` con 7 proveedores
- `LLMRouter` con selección por tarea

### A1 — API Congelada
51 tests de contrato. API pública documentada en `LLM_API.md`.
Firmas congeladas: `generate(prompt, model=None, options=None) -> str`.

### F19 — Resiliencia
- Circuit Breaker (CLOSED/OPEN/HALF_OPEN)
- Retry con backoff exponencial (solo errores transitorios)
- Fallback automático entre proveedores
- Health cache con TTL
- Observabilidad (latencia p50/p95/p99, throughput, tokens/s)
- Logging estructurado sin fugas de datos

### F20 — Profiling Continuo
- Profiler (wall time, cpu time, tracemalloc memory)
- Hotspot detector con ranking
- Performance baseline con percentiles y detección de regresiones
- Performance monitor unificado
- Benchmark integrado con `--monitor` flag

### F21 — Evaluación RAG
- Métricas: Recall@K, Precision@K, MRR, MAP, nDCG@K
- EvaluationEngine, Experiment framework
- Regression detection con baseline persistible
- Continuous evaluation con modo CI (pass/fail/warning)
- Benchmark CLI (`benchmark_rag.py`)

### F22 — 7 Proveedores
- Ollama (local), OpenAI (cloud), Anthropic (cloud)
- Gemini (cloud, 1M contexto), OpenRouter (proxy)
- LM Studio (local), vLLM (local, alta capacidad)
- Capability negotiation (vision, streaming, tools, etc.)
- Validación automática de proveedores (`validate_provider`)

### F23 — RC Validation
- Auditoría de API pública
- Eliminación de código muerto
- Documentación de deuda técnica
- Validación RC completa

## Cambios Incompatibles

No hay cambios incompatibles con la API pública documentada en `LLM_API.md`.
`config.local.json` está deprecated (eliminación prevista para F23 original,
pospuesta por `chattr +i` en `system_config.json`).

## Nuevas Capacidades

| Capacidad | Descripción | Fase |
|-----------|-------------|------|
| 7 proveedores LLM | Ollama, OpenAI, Anthropic, Gemini, OpenRouter, LM Studio, vLLM | F18/F22 |
| Circuit Breaker | CLOSED → OPEN → HALF_OPEN por proveedor | F19 |
| Retry automático | Backoff exponencial, solo errores transitorios | F19 |
| Fallback | Automático entre proveedores | F19 |
| Observabilidad | Latencia, throughput, tokens, errores por proveedor | F19 |
| Profiling | Wall time, CPU, tracemalloc | F20 |
| Evaluación RAG | Recall@K, MRR, MAP, nDCG, experimentos, regresiones | F21 |
| Secretos unificados | Backend env/file/default | F17.5 |
| Config unificada | UraConfig + CONFIG | F17 |

## Riesgos Conocidos

| Riesgo | Impacto | Estado |
|--------|---------|--------|
| 16 tests flaky bajo suite completo | Bajo | Todos pasan en aislamiento |
| `system_config.json` inmutable (`chattr +i`) | Medio | Workaround: `config.local.json` |
| Sin API keys cloud en entorno actual | Bajo | Solo Ollama local funcional |
| 7 copias de `_log_call` duplicadas | Bajo | Refactor post-RC |

## Limitaciones

1. **Tests flaky**: 16 tests fallan en suite completo por singletons globales.
2. **`chattr +i`**: `system_config.json` bloqueado, config en `config.local.json`.
3. **API keys**: Solo Ollama configurado localmente.
4. **7 copias de `_log_call`**: Código duplicado en cada proveedor.

## Requisitos de Despliegue

- Python 3.12+
- Ollama (para LLM local)
- Opcional: API keys para OpenAI/Anthropic/Gemini/OpenRouter
- Opcional: LM Studio o vLLM para inferencia local alternativa
- `motor.core.secrets`: variables de entorno o `/etc/ura/secrets.env`
- Sin dependencias externas más allá de `httpx`

## Artefactos de Documentación

| Documento | Descripción |
|-----------|-------------|
| `LLM_API.md` | API pública congelada |
| `API_AUDIT_v1_RC.md` | Auditoría de API |
| `PROVIDER_EXTENSION_GUIDE.md` | Guía para nuevos proveedores |
| `TECHNICAL_DEBT_v1_RC.md` | Deuda técnica documentada |
| `RC_VALIDATION_REPORT.md` | Reporte de validación RC |
| `FASE*_CLOSEOUT.md` | Actas de cierre (F15–F23) |

## Tags Relacionados

```
v0.18.0-fase18     — Cliente multiproveedor
v0.18.1-a1         — API congelada
v0.19.0-fase19     — Resiliencia
v0.19.1-f19-hardening — Hardening
v0.20.0-fase20     — Profiling
v0.21.0-fase21     — Evaluación RAG
v0.22.0-fase22     — 7 proveedores
v1.0.0-rc          — Release Candidate  ← NUEVO
```

### Fixes (RC→stable)
- Eliminados 16 tests flaky: sys.modules restaurado tras test de imports circulares
- 414/414 tests deterministas, 0 fallos
