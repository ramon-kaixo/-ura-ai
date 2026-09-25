# Arquitectura URA v6.0 — Documento de Referencia Única

> **Versión:** v6.0 (baseline: `de8229c1`)
> **Fecha:** 2026-09-25
> **Estado:** Fuente de verdad única para arquitectura actual

---

## 1. Visión General

URA es un asistente multi-agente de escritorio con:
- **Consciousness Coordinator** — coordinación central
- **Motor extensible** — plugins, hooks, eventos, pipelines
- **Agentes especializados** — organizados por dominio
- **Memoria larga** — fragmentos, KB, vectores
- **Plataforma** — protocolos, tracing, observabilidad

---

## 2. Estructura de Directorios

```
ura/
├── core/              # Dominio puro (consciente, valores, forense, rollback)
├── motor/             # Framework extensible (plugins, hooks, eventos, pipelines)
├── agents/            # Agentes especializados (por dominio en subdirectorios)
├── adapters/          # Conectores externos (LLM, notificaciones, KB)
├── knowledge/         # Memoria larga, fragmentos, KB, vectores
├── platform/          # Protocolos, tracing, observabilidad
├── intelligence/      # Agents runtime, memory, retrieval, consensus
└── scripts/           # Herramientas operativas (no librería)
```

---

## 3. Módulos Principales

### 3.1 `core/` — Dominio Puro
```
core/
├── agents/           # Agentes base (cocina, navegación, etc.)
├── debate/           # Motor de debate multi-agente
├── cleaner/          # Limpieza y mantenimiento
├── memoria/          # Memoria a corto plazo
├── mochila/          # Sistema de provisión LLM
├── auth_layer.py     # Capa de autenticación
├── change_guardian.py # Guardián de cambios
├── event_bus.py      # Bus de eventos interno
├── guardian_acciones.py # Guardián de acciones
└── qdrant_client.py  # Cliente Qdrant (proxy → motor)
```

### 3.2 `motor/` — Framework Extensible
```
motor/
├── agents/           # Runtime de agentes, memoria, retrieval
├── assistant/        # Asistente principal
├── brain/            # Cerebro coordinador
├── cli/              # CLI principal (ura)
├── config/           # Configuración (UraConfig = única fuente verdad)
├── core/             # Núcleo (secrets, config, exceptions, event_bus)
├── data/             # Datos persistentes
├── intelligence/     # Agents runtime, memory, retrieval, consensus
├── observability/    # Health, metrics, logging
├── platform/         # Protocolos, tracing, logging
└── core/             # Núcleo compartido
```

### 3.3 `agents/` — Agentes Especializados
Organizados por dominio en subdirectorios:
```
agents/
├── cocina/
├── navegacion/
├── programacion/
├── investigacion/
└── ... (otros dominios)
```

### 3.4 `knowledge/` — Memoria Larga
```
knowledge/
├── engine/           # Knowledge Engine (Fases 0-7)
├── fragmentos/       # Fragmentos de documentos
├── kb/               # Knowledge Base
├── vectorizar_docs/  # Vectorización de documentos
└── grafos/           # Grafos de conocimiento
```

### 3.5 `platform/` — Plataforma
```
platform/
├── protocols/        # Protocolos de comunicación
├── tracing/          # Tracing distribuido
├── observability/    # Métricas, health checks
└── logging/          # Logging estructurado
```

### 3.6 `intelligence/` — Inteligencia
```
intelligence/
├── agents/           # Runtime de agentes
├── memory/           # Memoria episódica, semántica
├── retrieval/        # Retrieval híbrido, reranking
└── consensus/        # Consenso multi-agente
```

---

## 4. Flujo de Datos Principal

```
Usuario → CLI (motor/cli) → Motor (motor/core) → Agentes (agents/) 
    ↓                              ↓
Config (UraConfig) → LLM (motor/core/llm) → Knowledge (knowledge/engine)
    ↓                              ↓
Platform (protocolos, tracing) ← Observabilidad (métricas, health)
```

---

## 5. Configuración

### 5.1 UraConfig — Fuente Única de Verdad
- **Ubicación:** `motor/core/config.py`
- **Carga:** `UraConfig.load(config_path)`
- **Prioridad:** legacy → CONFIG → env vars
- **Secrets:** `motor/core/secrets.py` (get_secret, require_secret)

### 5.2 Archivos de Configuración
- `motor/core/config.yaml` — Configuración principal
- `.env` — Variables de entorno (opcional)
- `/etc/ura/secrets.env` — Secrets (opcional)

---

## 5. LLM Providers

### Proveedores Soportados
- **OllamaProvider** (default) — Local, offline
- **OpenAIProvider** — API OpenAI
- **AnthropicProvider** — API Anthropic
- **GeminiProvider** — API Google
- **OpenRouterProvider** — API OpenRouter
- **LMStudioProvider** — Local LM Studio
- **VLLMProvider** — vLLM server

### Registro
- **ProviderRegistry** — Registro centralizado
- **LLMRouter** — Enrutamiento inteligente con circuit breaker

---

## 7. Protocolos y Observabilidad

### 7.1 Protocolos (motor/platform/)
- **ProtocolEnvelope** — 5 headers: Version, Routing, Trace, Delivery, Security
- **LocalTransport** — Transporte local
- **VersionNegotiator** — Negociación de versiones

### 7.2 Tracing
- **TraceExporter** — Exportador de trazas
- **MetricsCollector** — p50/p95/p99 latencias
- **HealthAggregator** — Agregador de health checks

### 7.3 Logging Estructurado
- **StructuredLogger** — JSON logging
- **TraceId/SpanId** — Correlación distribuida

---

## 8. Tests y Calidad

### 8.1 Métricas Objetivo v6.0
| Métrica | Target |
|---------|--------|
| Ruff errors | 0 |
| Mypy errors (core/motor/shared) | 0 |
| Tests passing | 100% (10,801/10,801) |
| Tests flaky | 0 |
| Cobertura core/ | ≥80% (meta 100x100) |
| Cobertura motor/ | ≥80% |

### 8.2 Estructura de Tests
```
tests/
├── unit/           # Tests unitarios
├── integration/    # Tests de integración
├── contracts/      # Tests de contrato (API pública)
├── infra/          # Tests de infraestructura
└── contracts/      # Tests de contrato
```

---

## 9. Referencias (ADRs Principales)

| ADR | Tema |
|-----|------|
| ADR-007 | Regla Núcleo (core/motor separation) |
| ADR-011-01 | Plugin API Contract |
| ADR-011-02 | EventBus Contract |
| ADR-011-03 | Hooks System |
| ADR-011-04 | Plugin Versioning |
| ADR-028 | Platform Protocols |
| ADR-099 | Mypy Strict Lessons |

---

## 10. Versionado y Releases

- **Esquema:** SemVer (MAJOR.MINOR.PATCH)
- **Tags:** `vX.Y.Z-faseN` para fases, `vX.Y.Z` para releases
- **Branching:** main + release/* + hotfix/*
- **CI/CD:** GitHub Actions (lint, typecheck, tests, security)

---

*Documento generado automáticamente como parte de Sprint 1 v6.0 (TASK-20260925-002)*
*Baseline: commit `de8229c1`*
*Fecha: 2026-09-25*
