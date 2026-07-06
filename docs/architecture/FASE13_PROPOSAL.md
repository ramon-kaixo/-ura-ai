# Propuesta — Fase 13: Producción

> **Versión:** 2.0
> **Fecha:** 2026-07-05
> **Estado:** 🟡 Planificado
> **Fase anterior:** Fase 12 (Inteligencia) — ✅ Cerrada v0.12.0
> **Objetivo:** Que otra persona pueda instalar URA y usarlo sin conocer el código

---

## Prerrequisitos para Iniciar (Go/No-Go)

| # | Requisito | Criterio |
|---|-----------|----------|
| G.1 | Fase 12 cerrada | ✅ `v0.12.0` |
| G.2 | Closeout aprobado | ✅ `FASE12_CLOSEOUT.md` |
| G.3 | Baseline generado | ✅ `v0.12.0` |
| G.4 | Plataforma estable | ✅ 889 tests, 0 failures |
| G.5 | Sin incidencias críticas | ✅ Deuda documentada, 0 críticas |

**Decisión:** Go ✅

---

## 1. Dependencias — Qué reutiliza F13 de F11/F12

| Componente | Uso en F13 | Estado |
|------------|------------|--------|
| Plugin System | Instalación de plugins vía pip + plugin discovery | Reutilizar |
| EventBus | Comunicación entre agentes para consenso | Reutilizar |
| Pipeline | Ejecución de workflows de CI/CD-like | Reutilizar |
| Memory (EpisodeStore) | Persistencia de sesiones, historial | Reutilizar |
| Memory (SemanticStore) | Almacenamiento de configuraciones | Reutilizar |
| Retrieval (Hybrid) | Búsqueda en documentación del sistema | Reutilizar |
| Multi-Agent Runtime | Orquestación de tareas de instalación/despliegue | Reutilizar |
| Observability (Metrics/Health) | Endpoints /metrics, /health para Prometheus | Reutilizar |

### Componentes nuevos necesarios

| Componente | Propósito |
|------------|-----------|
| Consensus Engine | Votación ponderada entre agentes |
| Dockerfile + docker-compose | Despliegue contenerizado |
| CLI setup/install commands | Experiencia de primera ejecución |
| Prometheus exporter | Formato OpenMetrics para /metrics |
| Documentación de usuario | README, QUICKSTART, PLUGIN_DEV |
| GitHub Actions CI/CD | Lint → test → build → release |

---

## 2. Orden de Implementación Recomendado

### Bloque 0 — Contratos (obligatorio antes de cualquier implementación)

| # | Artefacto | Depende de | Estado |
|---|-----------|------------|--------|
| 0.1 | ADR-013-01: Consensus Protocol | — | ⏳ Pendiente |
| 0.2 | ADR-013-02: Deployment & Observability | — | ⏳ Pendiente |

### Bloque 1 — Consenso entre Agentes

| # | Tarea | Esfuerzo | Depende de |
|---|-------|----------|------------|
| 1.1 | VotingEngine — votación ponderada | 3-4h | ADR-013-01 |
| 1.2 | WeightedConsensus — pesos por agente/rol | 2-3h | 1.1 |
| 1.3 | ReflectionAgent — autoevaluación de resultados | 3-4h | 1.1 |
| 1.4 | ParallelAgentExecutor — ThreadPool para subtasks | 2-3h | 1.1 |
| 1.5 | Tests: consenso, votación, reflexión, paralelo | 2-3h | 1.1-1.4 |

**Criterios de aceptación:**
- 3+ agentes con votación ponderada producen resultado reproducible
- ReflectionAgent mejora accuracy del resultado en ≥ 5%
- Ejecución paralela reduce tiempo total de workflow ≥ 30%
- 889 tests existentes siguen pasando

**Riesgos:** Deadlock en votación circular. Mitigación: timeout por agente (configurable).

### Bloque 2 — Infraestructura de Despliegue

| # | Tarea | Esfuerzo | Depende de |
|---|-------|----------|------------|
| 2.1 | Dockerfile multi-etapa (python:3.12-slim) | 2-3h | — |
| 2.2 | docker-compose.yml (api, ollama, qdrant) | 2-3h | 2.1 |
| 2.3 | Healthcheck en contenedor vía /health | 1h | 2.1 |
| 2.4 | Entrypoint con vars de entorno | 1-2h | 2.1 |
| 2.5 | Script install.sh (detecta SO, instala deps) | 3-4h | — |

**Criterios de aceptación:**
- `docker compose up` levanta todos los servicios en < 30s
- `docker run ura` funciona sin argumentos extra
- `/health` responde 200 en contenedor
- install.sh funciona en Ubuntu 24.04 clean

**Riesgos:** Ollama + Qdrant en Docker requieren GPU passthrough. Mitigación: documentar configuración GPU.

### Bloque 3 — Observabilidad Operativa

| # | Tarea | Esfuerzo | Depende de |
|---|-------|----------|------------|
| 3.1 | Exportador OpenMetrics en /metrics | 2-3h | — |
| 3.2 | Dashboard Grafana predefinido (JSON) | 3-4h | 3.1 |
| 3.3 | Reglas de alerta Prometheus | 2-3h | 3.1 |
| 3.4 | Logs estructurados JSON con correlation_id | 2-3h | — |

**Criterios de aceptación:**
- `curl /metrics` devuelve texto plano en formato OpenMetrics
- Dashboard Grafana importable con 5+ paneles
- Alerta dispara cuando un servicio está caído > 30s

**Riesgos:** Prometheus + Grafana añaden 2 contenedores extra. Mitigación: docker-compose opcional.

### Bloque 4 — Pipeline de Liberación

| # | Tarea | Esfuerzo | Depende de |
|---|-------|----------|------------|
| 4.1 | GitHub Actions CI (lint → test → build) | 3-4h | 2.1 |
| 4.2 | Release workflow (tag → publish pip + docker) | 3-4h | 4.1 |
| 4.3 | Paquete pip (`pip install ura`) | 3-4h | 2.1 |
| 4.4 | Smoke tests post-deploy | 2-3h | 4.2 |

**Criterios de aceptación:**
- `pip install ura` → `ura --help` funciona
- Push de tag → GitHub Actions publica pip + docker automáticamente
- Smoke tests verifican endpoints tras deploy

**Riesgos:** PyPI tiene restricciones de nombre. Mitigación: verificar disponibilidad del nombre.

### Bloque 5 — Documentación para Usuarios

| # | Tarea | Esfuerzo | Depende de |
|---|-------|----------|------------|
| 5.1 | README.md completo (instalación, ejemplos) | 3-4h | 2.x, 4.3 |
| 5.2 | QUICKSTART.md (primeros pasos en 5 min) | 2-3h | 2.x |
| 5.3 | CLI_REFERENCE.md (todos los comandos) | 3-4h | — |
| 5.4 | PLUGIN_DEV.md (cómo crear plugins) | 3-4h | — |
| 5.5 | OpenAPI/Swagger (endpoints públicos) | 2-3h | 3.x |

**Criterios de aceptación:**
- Usuario externo sin conocimiento del código puede instalar y ejecutar URA
- Documentación revisada por tercero

**Riesgos:** Documentación desactualizada rápidamente. Mitigación: generar desde código (OpenAPI, CLI --help).

### Bloque 6 — Deuda Técnica de F12 (seleccionada)

| # | Tarea | Esfuerzo | Deuda F12 |
|---|-------|----------|-----------|
| 6.1 | Cross-encoder fine-tuning con datos URA | 4-6h | D01 |
| 6.2 | LLM FactExtractor (ollama-based) | 3-4h | D02 |
| 6.3 | Consolidación automática episódica→semántica | 2-3h | D03 |
| 6.4 | Integración KE 2.0 + Memory (ContextRetriever) | 3-4h | D06 |

**Criterios de aceptación:**
- Cross-encoder fine-tuneado: MAP ≥ 0.85 en corpus de evaluación
- FactExtractor con LLM extrae relaciones no cubiertas por reglas
- Consolidación automática sin intervención manual

---

## 3. Riesgos Técnicos Principales

| # | Riesgo | Probabilidad | Impacto | Mitigación |
|---|--------|-------------|---------|------------|
| R1 | GPU passthrough en Docker (Ollama + Qdrant) | Alta | Medio | Documentar modo CPU-only y GPU. Fallback a CPU |
| R2 | Votación circular entre agentes (deadlock) | Baja | Alto | Timeout por agente + detección de ciclos |
| R3 | pip install falla por dependencias nativas (torch) | Media | Alto | Usar `pip install ura[all]` vs `ura[core]`. wheels precompilados |
| R4 | Prometheus + Grafana aumentan complejidad operativa | Media | Bajo | docker-compose opt-in. Documentar alternativa sin observabilidad |
| R5 | Documentación se desactualiza tras release | Media | Medio | Generar desde código (pydoc, OpenAPI, CLI args). CI verifica |

---

## 4. Criterios de Salida (F13 cerrada)

| # | Criterio | Medible |
|---|----------|---------|
| C.1 | Docker | `docker run ura` funciona con `URA_OLLAMA_URL` como única variable requerida |
| C.2 | pip install | `pip install ura && ura --help` funciona en Ubuntu 24.04 clean |
| C.3 | Consenso | 3 agentes votan y producen resultado reproducible en < 5s |
| C.4 | Prometheus | `curl localhost:8000/metrics` devuelve al menos 20 métricas distintas |
| C.5 | Grafana | Dashboard importable con latencia P50/P95, throughput, health |
| C.6 | CI/CD | GitHub Actions: push a main → tests → build. Tag → release |
| C.7 | Documentación | README, QUICKSTART, CLI, PLUGIN_DEV, OpenAPI — todos actualizados |
| C.8 | Sin regresiones | Mismos tests verdes que Fase 12 (889+ nuevos) |
| C.9 | Validación transversa | Closeout, tag v0.13.0, baseline comparado |

**Tiempo estimado total:** 8-12 días de trabajo efectivo (bloques 1-6).
