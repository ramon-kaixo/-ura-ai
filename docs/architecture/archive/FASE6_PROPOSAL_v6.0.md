# Fase v6.0 — Nueva Arquitectura / Release Mayor

## Contexto
- **Roadmap v0.x completado**: F10-F29, Post-F29 F1-F4, PM v3.1
- **UDO F3**: NO-GO (v0.30.0-f2, 2026-08-08)
- **Estado actual**: v5.7.1 + 2898 commits sin tag
- **UDO**: Operativa (modo secuencial, Web=ejecutor, TERM=revisor)

---

## Objetivos v6.0

### Objetivo Principal
**Consolidar, versionar y estabilizar la arquitectura actual para release v6.0**
- Eliminar gap de 2898 commits sin versión
- Resolver deuda técnica acumulada
- Establecer baseline sólido para evolución futura

### Objetivos Específicos

| # | Objetivo | Criterio de Aceptación |
|---|----------|------------------------|
| 1 | **Versionado semántico real** | Tag v6.0.0 con changelog completo desde v5.7.1 |
| 2 | **Deuda técnica a 0 crítico** | 0 ruff errors, 0 tests flaky, 0 mypy errors |
| 3 | **Arquitectura documentada** | docs/architecture/ actualizada, 1 fuente de verdad |
| 4 | **Tests 100% verdes** | 10,801 tests passing, 0 flaky |
| 5 | **Branching limpio** | Solo main + release branches, feature/* merged o deleted |
| 6 | **Release pipeline** | CI/CD para releases automáticos |

---

## Arquitectura Objetivo v6.0

### Módulos Core (Consolidados)
```
ura/
├── core/           # Dominio puro (consciente, valores, forense, rollback)
├── motor/          # Framework extensible (plugins, hooks, eventos, pipelines)
├── agents/         # Agentes especializados (por dominio)
├── adapters/       # Conectores externos (LLM, notificaciones, KB)
├── knowledge/      # Memoria larga, fragmentos, KB, vectores
├── platform/       # Protocolos, tracing, observabilidad
├── intelligence/   # Agents runtime, memory, retrieval, consensus
└── scripts/        # Herramientas operativas (no librería)
```

### Principios Arquitectónicos v6.0
1. **Separación estricta core/motor** (ADR-007)
2. **Plugin-first**: toda nueva funcionalidad = plugin
3. **Observabilidad nativa**: tracing, métricas, health checks
4. **Configuración unificada**: UraConfig = única fuente de verdad
5. **Secretos gestionados**: motor/core/secrets.py obligatorio
6. **Tests como documentación**: 100% cobertura por módulo nuevo

---

## Plan de Ejecución

### Sprint 1: Estabilización (2-3 semanas)
| Tarea | Esfuerzo | Responsable |
|-------|----------|-------------|
| 1.1 Fix test flaky (test_llm_contract) | 2h | WEB |
| 1.2 Resolver 93 ruff errors | 8h | TERM |
| 1.3 Limpieza ramas feature/* | 4h | WEB |
| 1.4 Documentación arquitectura actual | 8h | TERM |

### Sprint 2: Consolidación (3-4 semanas)
| Tarea | Esfuerzo | Responsable |
|-------|----------|-------------|
| 2.1 Consolidar docs/architecture | 16h | WEB |
| 2.2 Unificar configuración (validar UraConfig) | 8h | TERM |
| 2.3 Auditar secretos (motor/core/secrets.py) | 4h | WEB |
| 2.4 Pipeline release CI/CD | 16h | TERM |

### Sprint 3: Release v6.0 (1-2 semanas)
| Tarea | Esfuerzo | Responsable |
|-------|----------|-------------|
| 3.1 Changelog completo v5.7.1 → v6.0.0 | 4h | WEB |
| 3.2 Tag v6.0.0 + release notes | 2h | TERM |
| 3.3 Validación smoke tests completa | 4h | WEB |
| 3.4 Documentación release | 4h | TERM |

---

## Criterios de Calidad (Gate de Salida)

| Métrica | Target v6.0 |
|---------|-------------|
| Ruff errors | 0 |
| Mypy errors (core/motor/shared) | 0 |
| Tests passing | 100% (10,801/10,801) |
| Tests flaky | 0 |
| Cobertura core/ | ≥80% (meta 100x100 progresivo) |
| Cobertura motor/ | ≥80% |
| Documentación arquitectura | 100% actualizada |
| Branches activos | ≤5 (main + release/* + hotfix/*) |

---

## Estimación Total
- **Esfuerzo**: ~80-100h (3-4 sprints de 2 semanas)
- **Duración estimada**: 6-8 semanas
- **Riesgo**: MEDIO (deuda acumulada, tests flaky, ramas divergentes)

---

## Próximos Pasos Inmediatos
1. **TERM (revisor)**: Revisar esta propuesta → APROBADO / CAMBIOS_SOLICITADOS
2. Si APROBADO: Crear TASKs UDO por sprint
3. Iniciar Sprint 1 con asignación de roles

---

## Notas
- Esta propuesta sigue proceso UDO Anexo A (Web=ejecutor, TERM=revisor)
- Requiere gate de revisión antes de IN_PROGRESS en TASKs derivadas
- Baseline: commit `de8229c1` (HEAD actual)

---

*Generado por WEB (ejecutor) - TASK-20260925-001*
*Fecha: 2026-09-25*
