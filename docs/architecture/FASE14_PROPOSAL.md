# Fase 14 — Propuesta de Robusteces Operativas

> **Estado:** Planificación (sin implementación)
> **Depende de:** Cierre transversal F10–F13
> **Clasificación del proyecto:** Beta técnica avanzada (ver Release Review)

---

## Contexto

Tras el cierre transversal F10–F13, el proyecto ha alcanzado:

- 1,100 tests, 0 fallos
- Arquitectura modular con contratos (ABCs, ADRs)
- Retrieval híbrido con R@10=0.87 y NoCtx=0.5%
- Multi-Agent Runtime con consenso, reflexión y paralelismo
- Observabilidad completa (métricas, health, readiness, logging JSON)
- Despliegue Docker + CI/CD
- 46 elementos de deuda técnica catalogados (0 críticos, 4 altos)

La validación ha sido predominantemente estructural (tests unitarios e integración).
Para dar el salto a **producción** se necesita una fase centrada en robustez operativa.

---

## Orden de Ejecución Propuesto

**Bloque 1 → Bloque 2 → Bloque 3 → Bloque 4**

| Bloque | Descripción | Esfuerzo | Prioridad |
|--------|-------------|----------|-----------|
| **1** | CI/CD + Infraestructura | 5-8h | Alta (sin CI no hay producción) |
| **2** | Pruebas de carga y resiliencia | 10-16h | Alta |
| **3** | Migración legacy + saneamiento | 12-20h | Media |
| **4** | Documentación operativa | 6-10h | Media |

---

## Bloque 1 — CI/CD + Infraestructura (5-8h)

### Objetivo
Automatizar la validación completa en cada PR/release, cerrar los 4 elementos de deuda alta.

### Dependencias
- GitHub Actions (crear directorio `.github/workflows/`)
- Docker (build image en CI)

### Riesgos
- API keys expuestas en logs de CI
- Coste de ejecución de tests (82s → aceptable para CI)
- Docker build en CI requiere acceso a registry

### Criterios de Aceptación
- [ ] CI lanza en cada PR: ruff → pytest → py_compile → build wheel
- [ ] Release workflow: build → push image → publish PyPI
- [ ] Docker build verificado en CI
- [ ] Smoke tests post-deploy
- [ ] Benchmark comparativo en CI (aviso de regresión)

### Esfuerzo Estimado: 5-8h

### Subtareas sugeridas
1. Crear `.github/workflows/ci.yml` con lint + test + build (2h)
2. Crear `.github/workflows/release.yml` con PyPI + Docker Hub (2h)
3. Añadir benchmark comparativo a CI (1h)
4. Configurar Docker build en CI (0.5-1h)
5. Smoke test post-deploy (0.5-1h)
6. Pre-commit hooks + lint-staged (0.5h)

---

## Bloque 2 — Pruebas de Carga y Resiliencia (10-16h)

### Objetivo
Demostrar que el sistema soporta cargas realistas sin degradación,
y se recupera correctamente ante fallos de dependencias.

### Dependencias
- Sistema operativo con Docker (GX10 o similar)
- Qdrant + Ollama accesibles

### Riesgos
- Ollama requiere GPU para benchmarks realistas
- Qdrant puede saturarse con alta concurrencia
- Resultados dependientes del hardware

### Criterios de Aceptación
- [ ] Stress test: 100 queries concurrentes (P95 < 2s, 0 errores)
- [ ] Soak test: 1000 queries en 10 minutos (sin leak de memoria, sin degradación)
- [ ] Resiliencia Qdrant: sistema degrada y restaura correctamente
- [ ] Resiliencia Ollama: sistema maneja timeout y recuperación
- [ ] Resiliencia Redis (si aplica): reconexión automática
- [ ] Circuit breaker: se abre tras N fallos, se cierra al recuperar
- [ ] Documentación de límites conocidos (máx queries, capacidad memoria)

### Esfuerzo Estimado: 10-16h

### Subtareas sugeridas
1. Diseñar suite de stress/soak tests con locust o script propio (3h)
2. Ejecutar baseline de carga contra F13 (1h)
3. Tests de resiliencia: caída Qdrant, Ollama, Redis, red (4h)
4. Verificar DegradedMode en todos los subsistemas (2h)
5. Documentar límites de capacidad conocidos (2h)
6. Integrar tests de resiliencia en CI (2h)

---

## Bloque 3 — Migración Legacy + Saneamiento (12-20h)

### Objetivo
Eliminar la deuda arquitectónica más pesada: duplicación de config,
código muerto en `core/` y `knowledge/`, ABCs duplicados.

### Dependencias
- ADR-007 (Core Modification Rule) — requiere revisión de segundo par
- Tests existentes como red de seguridad

### Riesgos
- Regresiones en funcionalidad legacy no testeada
- Ruptura de scripts que dependen de rutas antiguas
- ADR-007 exige plan de rollback y degradación

### Criterios de Aceptación
- [ ] `core/config.py` eliminado (todo apunta a `motor/core/config.py`)
- [ ] `core/qdrant_client.py` eliminado (todo apunta a `motor/core/qdrant_client.py`)
- [ ] BaseReranker duplicado fusionado en una sola ABC
- [ ] 33 bloques `except: pass` auditados y documentados individualmente
- [ ] 17 `type: ignore` resueltos o justificados
- [ ] ~106 S603/S607 migrados a API de alto nivel o auditados
- [ ] `CHANGELOG.md` actualizado
- [ ] Ruff errors reducidos en un 10% (de 2,446 a <2,200)

### Esfuerzo Estimado: 12-20h

### Subtareas sugeridas
1. Fusionar proxys de config y qdrant_client (2h)
2. Fusionar BaseReranker duplicado (0.3h)
3. Auditar y documentar cada bloque `except: pass` (3h)
4. Resolver `type: ignore` con tipado correcto (2h)
5. Migrar subprocess S603/S607 a API segura (4h)
6. Limpiar estilo Ruff (3h prioritario + 5h completo)
7. Actualizar CHANGELOG y documentación (1h)

---

## Bloque 4 — Documentación Operativa (6-10h)

### Objetivo
Completar la documentación para operadores y desarrolladores externos.

### Dependencias
- Bloque 1 (CI/CD funcionando para badges)
- Bloque 3 (migración legacy completada para docs precisas)

### Riesgos
- Documentación se desactualiza rápidamente sin CI que la valide
- Bajo ROI si el proyecto no tiene usuarios externos

### Criterios de Aceptación
- [ ] README.md con badges de CI, coverage, version, Python version
- [ ] `CONTRIBUTING.md` con guía de PRs y estándares
- [ ] `CODE_OF_CONDUCT.md`
- [ ] `LICENSE` file explícito
- [ ] `.dockerignore` para builds rápidos
- [ ] Documentación de API REST (OpenAPI 3.0)
- [ ] Guía de operación: deploy, backup, restore, troubleshooting
- [ ] `SECURITY_EXCEPTIONS.md` actualizado

### Esfuerzo Estimado: 6-10h

### Subtareas sugeridas
1. Actualizar README con badges y secciones (1h)
2. Crear CONTRIBUTING.md (1h)
3. Añadir LICENSE file (0.2h)
4. Añadir .dockerignore (0.1h)
5. Documentar API REST con OpenAPI (2h)
6. Guía de operación (2h)
7. Actualizar SECURITY_EXCEPTIONS.md (0.3h)
8. Validar todos los enlaces de documentación (1h)

---

## Resumen de Esfuerzo

| Bloque | Esfuerzo | Prioridad | Riesgo Principal |
|--------|----------|-----------|-----------------|
| 1 — CI/CD + Infra | 5-8h | 🔴 Alta | API keys en CI |
| 2 — Carga/Resiliencia | 10-16h | 🔴 Alta | Resultados HW-dependentes |
| 3 — Migración Legacy | 12-20h | 🟡 Media | Regresiones en código legacy |
| 4 — Documentación | 6-10h | 🟢 Media | Desactualización rápida |
| **Total** | **33-54h** | **Mixta** | — |

---

## Dependencias Externas

| Dependencia | Para | Alternativa |
|-------------|------|-------------|
| GPU NVIDIA (GX10) | Benchmarks de embedding/retrieval | CPU-only con degradación |
| Qdrant en Docker | Tests de resiliencia | Mock QdrantClient |
| Ollama + modelos | Tests e2e multi-agente | Mock Agent base |
| GitHub Account | CI/CD workflows | GitLab / Gitea self-hosted |
| PyPI API token | Publicación pip | GitHub Releases como fallback |

---

## Criterios de Aceptación Globales (F14)

- [ ] CI/CD operativo: lint + test + build en cada PR
- [ ] Release workflow publicado
- [ ] Stress test: 100 queries concurrentes sin error
- [ ] Resiliencia probada: Qdrant, Ollama, red
- [ ] Deuda alta (4 items) resuelta
- [ ] Deuda media (14 items) reducida en un 50%
- [ ] 0 regresiones funcionales vs F13
- [ ] Documentación operativa completa

---

## Riesgos Identificados

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|-------------|---------|------------|
| Regresiones por migración legacy | Alta | Alto | Tests existentes + rollback plan (ADR-007) |
| Benchmarks no reproducibles | Media | Medio | Dockerizar benchmarks + fijar seed |
| CI/CD bloqueado por secrets | Baja | Alto | Usar GitHub Environments + secrets |
| Documentación obsoleta | Alta | Bajo | CI que valida enlaces + schema checks |
| Sin GPU para benchmarks | Media | Alto | Modo degraded para CPU-only |

---

## Decisión

**No comenzar implementación de F14 sin aprobación explícita.**

La planificación asume un bloque → bloque secuencial (1→2→3→4), pero los bloques
1 y 2 podrían ejecutarse en paralelo con recursos suficientes.

Tras F14, si todos los criterios se cumplen, el proyecto puede clasificarse como
**producción** con confianza.
