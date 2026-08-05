# Backlog de URA — Pendiente priorizado

**Última actualización:** 2026-08-05
**Regla:** todo trabajo pendiente vive aquí. Al completar un ítem, mover a "Completado" con fecha y commit.

## P0 — Crítico (bloquea o rompe)

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-40 | Soak 1M ops (test_f25_b7_hardening) NO completa en 600s — problema de rendimiento real en fact_history | Test inviable + señal de lentitud | Marcado slow (fuera de validate); investigar fact_history con 1M versiones (rollback/timeline) | 🟡 documentado |

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-01 | 5 tests flaky en suite completa (degraded_mode, f27_b8_hardening, daemon dashboard, cleanup_integration, contextual_retrieval, f25_b6_fact_history) | Falsos rojos en validate | Aislar estado compartido (threads/asyncio); algunos son del otro agente — coordinar | 🟡 documentado, pasan aislados |
| B-02 | make validate ~7-9 min (>5 min objetivo) | Iteración lenta | Sin xdist (satura host): reducir suite, marcar más slow, o dividir validate | 🟡 |
| B-03 | 4 servicios systemd en crash-loop (model-router, ura-capturador, ura-voice, ura-openclaw) | CPU quemada | Ramón: `sudo systemctl stop` (sin sudo desde aquí — rootfs RO) | 🔴 pendiente Ramón |

## P1 — Alta (deuda que crece)

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-10 | Violaciones xenon (complejidad) | Mantenibilidad | **2 rank D eliminados** (cmd_doctor, cmd_audit); quedan 6 C en cmd_ura.py; refactor progresivo | 🟡 98 C / 0 D |
| B-11 | Timers systemd generados (deploy/timers/) NO instalados | Automatización incompleta | `sudo cp deploy/timers/* /etc/systemd/system/` + daemon-reload | 🔴 requiere sudo |
| B-12 | Fases 3-4 Plan de Testing: snapshot (5+), locust, mutmut nocturno, chaos integrado | Validación incompleta | tests/snapshot/, tests/load/, mutmut config, make chaos | 🔮 (Fase 2 ✅ 14 tests property) |
| B-13 | quality_gate sin validar contra reporte real (th thresholds) | Thresholds no probados | Cuando el lock se libere: make tuneladora → quality_gate con reporte real | 🟡 |

## P2 — Media

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-20 | 8 scripts huérfanos | Ruido | **✅ Archivados** (verificados 0 conexiones) | ✅ |
| B-21 | Coverage por módulo en reporte JSON depende de coverage.xml (no siempre presente) | Regresión por módulo invisible | Ejecutar pytest con --cov en phase_dynamic cuando sea viable | 🟡 |
| B-22 | docs/API.md | Bloquea load testing | **✅ Creado con 36 endpoints verificados** | ✅ |

## P3 — Baja / Mejoras

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-30 | Catálogo de decisiones pequeñas (docs/DECISIONES.md) | Pérdida de contexto | Crear y mantener | 🔮 |
| B-31 | Registro de evidencias | Sin prueba objetiva | **✅ capturar_evidencias.py** (tests/complejidad/git/auditoría) | ✅ |
| B-32 | LLM Gateway para OpenCode+OpenClaw (exponer motor/core/llm como HTTP) | Configuración duplicada | Servicio sobre motor/core/llm/router + docs | 🔮 |
| B-33 | make test-suite en CI/pre-push | Validación previa a push | Añadir al hook pre-push (lento — evaluar) | 🔮 |

## Completado recientemente

| ID | Ítem | Commit |
|---|---|---|
| C-01 | 6 gaps Plan Maestro Tuneladora | d81bba94...a0e037ee |
| C-02 | Día 2: notifier/coverage/QG/hooks/ADR/auditoría/timers/orquestador/docs | 5c5c8fad...6bd3b5df |
| C-03 | Testing Fase 1 (randomly, deadfixtures, radon, xenon) | 77b0f146 |
| C-04 | Fail-safe QG (coverage 0 no bloquea) | 6f8f03c0 |
