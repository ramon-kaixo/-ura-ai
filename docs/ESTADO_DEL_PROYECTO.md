# Estado del Proyecto URA — Documento Vivo

**Última actualización:** 2026-08-05
**Criterio:** este documento se actualiza al cierre de cada fase/sesión. Si dice algo distinto del código, el código manda (y se corrige el documento).

## Estado general

| Dimensión | Valor | Tendencia |
|---|---|---|
| Git | limpio (0 sin commit) | ✅ |
| Tests | **6,347** coleccionan, 0 errores | ↑ (6,274 → 6,347) |
| Cobertura global | ~78.4% (motor 86%, core 78.7%, knowledge 64.5%) | = |
| Complejidad promedio | A (3.03) | ✅ objetivo |
| Violaciones xenon (umbral B) | **158** | 🔴 deuda |
| Flaky en suite completa | 5 conocidos (todos pasan aislados) | 🟡 |
| make validate | ~7-9 min | 🟡 (>5 min objetivo) |
| Reportes tuneladora generados | 208 | ✅ pipeline operativo |
| Commits | 1,401 | — |
| Docs | 50 | — |

## Arquitectura (5 bloques)

1. **Gobernanza**: orquestador (8 fases), backlog, ADRs (hasta 221), criterios, reglas
2. **Desarrollo**: contexto → plan → implementación → revisión (orquestador + tuneladora)
3. **Validación**: pytest + ruff/mypy/bandit + randomly + deadfixtures + radon/xenon + auditoria_paralela
4. **Conocimiento**: 4 capas de memoria + 3 capas del proyecto + docs
5. **Entrega**: reportes JSON tuneladora + notificador + evidencias + estado

## Pipelines activos (6)

| Pipeline | Trigger | Estado |
|---|---|---|
| tuneladora (16 fases) | manual/scheduler/hook | ✅ |
| scheduler (health 5min/cleanup 60min/audit 360min) | systemd | ✅ |
| auditoria_continua | timer 5min + make audit | ✅ |
| auditoria_paralela (10 checks) | make audit | ✅ |
| orquestador (8 fases) | manual | ✅ |
| test-suite (random+dead+complexity) | make test-suite | ✅ (Fase 1) |

## Incidencias abiertas (resumen — ver BACKLOG.md)

1. 158 violaciones de complejidad (refactor progresivo)
2. 5 flaky de concurrencia en suite completa
3. make validate > 5 min (sin xdist — satura host)
4. Timers systemd generados pero NO instalados (requiere sudo)
5. rootfs RO: sudo no disponible → crash-loops pendientes de Ramón
6. Fases 2-4 del Plan de Testing sin ejecutar (property/snapshot/load/mutmut/chaos)
7. 8 scripts huérfanos en scripts/pro (purga parcial)
8. quality_gate sin reporte real para validar thresholds (el lock lo usa el otro agente)

## Última auditoría

**2026-08-05 (auditoria_paralela):** 10/10 checks OK (memorias, supervisor, quality gate, lock stale, tests, huérfanos, duplicados, imports, secretos, rendimiento)

## Roadmap

| Fase | Objetivo | Estado |
|---|---|---|
| Núcleo (Plan Maestro Tuneladora) | 6 gaps cerrados, ADN documentado | ✅ |
| Día 2 (Automatización) | notifier, coverage, QG, hooks, ADR, auditoría, timers, orquestador, docs | ✅ |
| Testing Fase 1 | randomly, deadfixtures, radon, xenon | ✅ |
| Testing Fase 2 | 10+ tests property-based (tests/property/) | 🔮 |
| Testing Fase 3 | 5+ snapshots + locustfile + docs/API.md | 🔮 |
| Testing Fase 4 | mutmut nocturno + chaos integrado | 🔮 |
| Reducción complejidad | 158 → <50 violaciones xenon | 🔮 |
| LLM Gateway (OpenCode+OpenClaw) | exponer motor/core/llm como servicio | 🔮 |
