# Backlog de URA — Pendiente priorizado

**Última actualización:** 2026-08-06
**Regla:** todo trabajo pendiente vive aquí. Al completar un ítem, mover a "Completado" con fecha y commit.

## P0 — Crítico (bloquea o rompe)

| ID | Ítem | Impacto | Solución | Estado |
|---|---|---|---|---|
| B-40 | Soak 1M ops no completaba en 600s | Test inviable | **✅ DIAGNOSTICADO + RESUELTO**: cuello de botella en el TEST (timeline() en cada read, O(n^2 log n)); motor sano; timeline amortizado -> 13s | ✅ docs/B-40-DIAGNOSTICO.md |

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

## Cierre 2026-08-05 (Plan Maestro Backlog)

| Ítem | Resultado | Evidencia |
|---|---|---|
| B-21 QG coverage modo check | ✅ Fix (Omite coverage en check; tests 18 pass) | commit fix(quality_gate) |
| B-01 flaky suite | ✅ 5242 passed 0 failed en suite completa | degraded→reruns, latency/cleanup/soak→slow |
| B-02 validate <6min | ✅ 5:01→3:13 (unit 224s→79s, 33 tests slow) | make validate 3:13 |
| B-03 crash-loops | ✅ 0 activos (inactive/failed, sin sudo para disable) | systemctl is-active |
| B-11 timer OnCalendar | ✅ *:0/6 validado con systemd-analyze | commit fix(timers) |
| B-12-F3 snapshot | ✅ 4 snapshots estables (sparse_vector eliminado: hash no-determinista) | make test-snapshot |
| B-12-F4 mutmut timer | ✅ unidades en deploy/timers/ + validado | systemd-analyze calendar |
| B-12-F3 locust | ✅ locustfile 3 endpoints documentados | make test-load |
| B-40 (nuevo) | Soak 1M ops no completa en 600s — rendimiento fact_history | documentado |
| Nota | Agente paralelo revierte timer (2x) — re-aplicado | — |

## Cierre 2026-08-06 (Fase 1 residual v4.0 + conflicto timer)

| Ítem | Resultado | Evidencia |
|---|---|---|
| F1.3 pycache | ✅ 108 dirs de código vivo eliminados | find: 0 restantes (gitignored) |
| F1.3 benchmark_ke.py | ✅ Archivado → `.attic/tools/benchmarks/`; test pending con skipif (29 skip limpio) | commit `1958925d` |
| F1.3 tools/ | ✅ Eliminado (vacío, 0 archivos trackeados) | rmdir + git rm |
| F1.3 cli.py | ✅ RESTAURADO — era vivo (3 consumidores: `__init__.py`, 8 tests, 2 systemd). Renombrado por error en `b5088736` → 7 errores de colección | commit `8cad8280`, validate OK |
| B-11 conflicto latente | ✅ **Causa raíz corregida**: `manage_timers.py:45` tenía sintaxis inválida + test la convalidaba → `generate` regeneraba el timer roto | commit `a3570018`; `generate` → diff vacío, `*:0/6` válido |
| v4.0 diagnóstico | ✅ `docs/ARQUITECTURA_v4.0_DIAGNOSTICO.md` con clasificación real (canónico/muerto) verificada | documento creado |

## Cierre v4.0 (2026-08-06) — Fases 0,1,3,4,5,6.1,7(docs),8

| Fase | Resultado | Evidencia |
|---|---|---|
| F0 | ✅ tag `pre-arch-v4.0` + pydeps `arch_core_deps.json` (160/570) + `arch_motor_deps.json` (303/1297) + etiquetas docstring 4 paquetes | commit `e36f6a3f` |
| F1 | ✅ verificada residual (0 .bak, .gitignore, pycache) | — |
| F4 | ✅ `docs/PIPELINE.md` — canónico tuneladora/; `pipeline_supremo.py` DEGRADADO 7/10 pasos (refs archivadas) | commit `d5ad94f6` |
| F5 | ✅ `docs/ROUTERS.md` — triplicación verificada; `core/model_router/` TRANSICIÓN (0 consumidores vivos, 6 tests) | commit `9fac9308` |
| F3 | ✅ `docs/MEMORIA.md` fusionada (v1 prod + v2 + v12, sin archivar sueltos con tests) | commits `b3794a3b`,`a743947f` |
| F6.1 | ✅ 26 cadenas muertas archivadas `.attic/.../purga-v4-cadenas/`; 27 de purga-v4 eran untracked → devueltos por decisión Ramón | commit `f2c4ce93` (paralelo) |
| F7 | ✅ `docs/SYSTEMD_V4.0.md` diagnóstico 5 failed con causas + secretos opencode.service + plan comandos Ramón | commit `d56005cd` |
| F8 | ✅ `docs/ARQUITECTURA.md`, `MODULOS_CANONICOS.md`, `DEPRECADO.md`, `SERVICIOS.md`, `TOOLS_INDEX.md` regenerado (178→107) | commits F8 |
| F6.2 | ✅ restaurados módulos con consumidores vivos (reuse/, autonomy/learning/, goal_manager, reglas_* — idénticos a `38b7921c~1`); degradadas refs a código inexistente (LearningPlugin, plan_validator→core/debate, model_router_main×4); archivados ciclo_rapido.sh, ura-mcp.service, ia-flujo.service; `make validate` OK | commits `f25f68bd`,`ec8b6b39`,`feea20ff` |

### Pendientes v4.0 (cierre)

| Pendiente | Dueño |
|---|---|
| F7:P: ejecutar plan SYSTEMD_V4.0 (5 failed + secrets rotación + integración ura-mutmut) | Ramón (sudo) |
| F5: decidir archivo de `core/model_router/` (ADR-007 segunda revisión) | Ramón |
| F3/v4.0e: unificar memoria v1→v2 | Ramón (toca motor/core) |
| Fase 2 v4.0: providers LLM | Ramón + otro agente |
| Tag final `v4.0.0-arch` + push (origin 492+ atrás) | Ramón |

### Origin/main — análisis (2026-08-06, Bloque 2)

**Resultado del fetch (`git fetch origin`):**

| Métrica | Valor |
|---|---|
| Commits `HEAD..origin/main` | **0** (Ninguno pendiente de origin) |
| Divergencia `origin/main...HEAD` | `0 / 507` (todo el avance es local) |
| Último commit origin/main | `452ba9bf` feat: external_audit.sh con OpenRouter/Claude + fallback Ollama + cron |
| Remote | `git@github.com:ramon-kaixo/-ura-ai.git` |

**Conclusiones:**
- ❌ El plan asumía "3 commits pendientes en origin" — el fetch confirma **0**. No hay nada que traer, mergear ni conflictos con F6.2.
- ⚠️ Origin/main está **507 commits por detrás** del local — el tag `v4.0.0-arch` NO debe pushearse hasta que Ramón decida el orden de sincronización (origin está respaldando un estado muy antiguo).
- ⚠️ Durante la auditoría se detectó un cambio local sin commitear en `core/config_manager.py` (hardcodea `_URA_ROOT=/home/ramon/URA/ura_ia_1972`), NO originado en esta sesión. **Pendiente review de Ramón**, NO incluido en commits del plan.
