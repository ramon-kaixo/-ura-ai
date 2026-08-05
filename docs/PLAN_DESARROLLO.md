# Plan de Desarrollo de URA — Especificación Técnica Ejecutable

**Fecha:** 2026-08-05
**Referencia:** Estado en docs/ESTADO_DEL_PROYECTO.md · Pendiente en docs/BACKLOG.md

## Arquitectura objetivo: 5 bloques

```
┌────────────────────────────────────────────────────────────┐
│  GOBIERNO   orquestador · backlog · ADRs · criterios        │
│             parada/aceptación · reglas                      │
├────────────────────────────────────────────────────────────┤
│  DESARROLLO contexto → plan → implementación → revisión     │
│             (orquestador 8 fases + tuneladora)              │
├────────────────────────────────────────────────────────────┤
│  VALIDACIÓN pytest · ruff/mypy/bandit · randomly ·           │
│             deadfixtures · radon/xenon · hypothesis ·        │
│             snapshot · mutmut · chaos · auditoría paralela   │
├────────────────────────────────────────────────────────────┤
│  CONOCIMIENTO memorias (4+3 capas) · inventarios ·           │
│             decisiones · deuda técnica · capacidades         │
├────────────────────────────────────────────────────────────┤
│  ENTREGA    evidencias · informe · notificación · estado     │
└────────────────────────────────────────────────────────────┘
```

## Componentes por bloque

### Gobernanza (existente + faltante)
| Componente | Estado |
|---|---|
| Orquestador (8 fases) | ✅ scripts/pro/orquestador.py |
| Backlog | ✅ docs/BACKLOG.md (NUEVO) |
| ADRs | ✅ hasta ADR-221 |
| Criterios de parada/aceptación | ✅ docs/CRITERIOS.md |
| Reglas para OpenCode | ✅ docs/OPENCODE_CAPACIDADES.md (NUEVO) + TESTING.md |
| Catálogo de decisiones | ✅ docs/DECISIONES.md (NUEVO) |
| Estado del proyecto | ✅ docs/ESTADO_DEL_PROYECTO.md (NUEVO) |

### Desarrollo
| Componente | Estado |
|---|---|
| Contexto (inventario + memorias) | ✅ auditoria_real + MEMORIA.md; ⏳ falta índice de capacidades vivo |
| Plan previo obligatorio | ✅ orquestador fase planificacion |
| Implementación | ✅ manual/OpenCode |
| Revisión de código | ✅ tuneladora + Sofia (LLM) |
| Revisión arquitectónica | ✅ xenon + auditoria_paralela |

### Validación
| Componente | Estado |
|---|---|
| pytest unit+integration | ✅ 6,347 |
| ruff/mypy/bandit | ✅ |
| pytest-randomly | ✅ Fase 1 |
| pytest-deadfixtures | ✅ Fase 1 (1 muerta eliminada) |
| radon/xenon | ✅ Fase 1 (158 violaciones — backlog B-10) |
| hypothesis | ⏳ Fase 2 (tests/property/) |
| pytest-snapshot | ⏳ Fase 3 |
| locust | ⏳ Fase 3 |
| mutmut | ⏳ Fase 4 (instalado, sin config nocturna) |
| chaos_test | ⏳ Fase 4 (integración make chaos) |

### Conocimiento
| Componente | Estado |
|---|---|
| Memorias (4 capas tuneladora + 3 del proyecto) | ✅ |
| Inventario de herramientas | ✅ TOOLS_INDEX + auditoria_real |
| Índice de capacidades (qué hace cada herramienta) | ⏳ NUEVO propuesto |
| Deuda técnica formal (IDs) | ✅ docs/DEUDA_TECNICA.md (actualizar formato) |
| Decisiones | ✅ docs/DECISIONES.md (NUEVO) |
| Capacidades de OpenCode | ✅ docs/OPENCODE_CAPACIDADES.md (NUEVO) |

### Entrega
| Componente | Estado |
|---|---|
| Reportes JSON tuneladora | ✅ 208 generados |
| Notificador de fallos | ✅ |
| Informe final (orquestador) | ✅ logs JSON |
| Registro de evidencias | ⏳ NUEVO propuesto (data/evidencias/) |
| Actualización de estado | ✅ docs/ESTADO_DEL_PROYECTO.md (NUEVO) |

## Roadmap de ejecución (orden de prioridad)

1. **BACKLOG P0**: flaky (B-01), validate tiempo (B-02) — requieren investigación profunda
2. **BACKLOG P1**: complejidad 158 → reducir módulos rank D primero; timers (sudo — Ramón)
3. **Testing Fase 2**: tests/property/ con 10+ tests hypothesis (4h)
4. **Testing Fase 3**: tests/snapshot/ (5+) + docs/API.md + locustfile (4h)
5. **Testing Fase 4**: mutmut nocturno + make chaos (2h)
6. **Índice de capacidades**: docs/CAPACIDADES_HERRAMIENTAS.md (catálogo vivo)
7. **Registro de evidencias**: script captura + data/evidencias/
8. **LLM Gateway**: exponer motor/core/llm como servicio HTTP para OpenCode+OpenClaw
9. **Segunda purga**: 8 huérfanos confirmados
10. **Módulos de negocio** (tras estabilizar backlog P0-P1)

## Criterios de parada (por pipeline)

| Pipeline | Parar si... |
|---|---|
| orquestador | fase falla → para y reporta (ya implementado) |
| tuneladora | verdict FAIL → rollback + notifica (ya implementado) |
| auditoria_paralela | check crítico falla (secretos/imports) |
| testing | make validate falla → no continuar (regla) |
| desarrollo de módulo | coverage baja, complejidad sube, cambios fuera de alcance |

## Criterios de aceptación (por pipeline)

| Pipeline | Aceptar si... |
|---|---|
| módulo implementado | tests + 0 errores collection + git limpio |
| fase cerrada | closeout + ADR (si decisión) + backlog actualizado |
| refactor | xenon no empeora + tests pasan + cobertura no baja |
| testing fase | make test-suite pasa + métricas objetivo alcanzadas |
