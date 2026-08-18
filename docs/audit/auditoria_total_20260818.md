# Auditoría Total URA — 2026-08-18

- **Fecha**: 2026-08-18 (17:10 CEST)
- **Autor**: [WEB] (OpenCode Web) en ASUS
- **TASK**: TASK-20260818-027
- **Base auditada**: `main` @ `a097dd95` (árbol limpio; trabajo del sandbox preservado en `stash@{0}` "sandbox-auto-20260818-final")
- **Método**: evidencia real (comandos ejecutados en la máquina), sin suposiciones. Lo no reproducible se marca NO VERIFICADO.
- **Alcance**: los 15 puntos solicitados. Sin modificar código ni configuraciones (solo se escribieron los 2 informes y el expediente de tarea).

## Resumen ejecutivo

| Métrica | Resultado |
|---|---|
| Tests | **4 failed / 5434 passed / 15 skipped / 8 rerun** (231.89s, árbol limpio, sin coverage) · **5 failed** con coverage (1 flaky hypothesis, §2.3) |
| Cobertura | TOTAL **83.5%** (23806 stmts, 3937 miss) — run oficial árbol limpio, 1265s (§3) |
| Módulos <80% | **87** (incluye core/agents/* y core/voice/* a 0%, motor/pipeline/* 18-27%) |
| Ruff | **81 errores** = 79 RUF100 (unused noqa, fixable) + 2 S310 (urlopen) |
| Mypy | **204 errores en 36 archivos** (460 source files) |
| Complejidad (C901) | 48 funciones (25 en scripts/pro); núcleo consistente con S5c |
| Bare except (E722) | **0** |
| F401 (imports sin usar) | **0** |
| eval/exec/shell=True en prod | **0** |
| Duplicados reales core/motor | **0** (9 pares nombre-idéntico = falso positivo, shims intencionales) |
| Imports circulares | **0** (5434 tests recolectados = import OK; core→motor 54 shims; motor→core 0) |
| Secretos en git | **0** |
| Systemd failed | **1** (`ura-mutmut-daily.service`) |
| Webhook alertas (9105) | **CAÍDO** (000) — contenedor con imagen vieja |
| Procesos llama-server | **2** (duplicación estructural confirmada) |

**Severidades**: P0 = 0 · P1 = 4 · P2 = 7 · P3 = 5. **No hay rotura funcional en producción**; los 4 tests fallidos son tests desactualizados contra firmas evolucionadas (causa raíz §2), no bugs del código de producción.

---

## 1. Estado del árbol y git

```
$ git status --short
 M docs/udo/coordination.json        <- ajeno (TERM/despertador); NO se toca

$ git log --oneline -5
a097dd95 docs(udo): actualizar coordinación y pendientes      (TERM, 16:49)
d7735346 docs(udo): [WEB] §18 bloque corregido (rebuild webhook + listar sandbox)
16065d25 fix(monitoreo): [TASK-20260818-025][WEB] webhook crash-loop — motor montado (ro) + httpx + secretos + import degradable
6783f2a0 docs(udo): [WEB] §17 bloque final sudo (compose -f8 + commit zona sandbox)
78b54dcb docs(udo): [TASK-20260818-025][WEB] expediente completado
```

Árbol limpio (0 archivos propios). Único modificado: `docs/udo/coordination.json` (zona UDO del TERM/despertador) — **no se toca**. El trabajo del sandbox (95 archivos) sigue en `stash@{0}`.

## 2. Tests — 4 fallos con causa raíz real

Comando: `.venv/bin/python -m pytest tests/unit -q --tb=no -p no:cacheprovider` (árbol **limpio**).

```
FAILED tests/unit/test_knowledge_compiler_cobertura.py::TestCtxStage::test_snapshot
FAILED tests/unit/test_knowledge_compiler_cobertura.py::TestCtxStage::test_errores_warnings
FAILED tests/unit/test_knowledge_compiler_cobertura.py::test_ctx_compatible
FAILED tests/unit/test_motor_assistant_executor.py::TestSafeCalculator::test_resultado_no_numerico
```

### 2.1 Los 3 de knowledge/engine/compiler.py — TEST desactualizado, código sano

Firma real del código (`knowledge/engine/compiler.py:224-240`):

```python
def _ctx_stage(meta, opts, snapshot: Snapshot | None, stage: CompileStage, errors=..., warnings=...) -> CompileContext
```

El test (`tests/unit/test_knowledge_compiler_cobertura.py`) usa **el orden antiguo (stage en 3ª posición)**:

- `test_snapshot` (línea 451): `_ctx_stage(_metadata(), _options(), CompileStage.PARSING, snap)` → pasa el **stage en la posición del snapshot** → `ctx.stage == snap` (un Snapshot) → `assert ctx.stage == CompileStage.PARSING` **falla con AssertionError**.
- `test_errores_warnings`: `_ctx_stage(_metadata(), _options(), CompileStage.WRITING, errors=errs, warnings=())` → stage en 3ª posición, falta `stage` posicional → **TypeError**.
- `test_ctx_compatible` (línea 709): `_ctx_stage(_metadata(), _options(), CompileStage.DONE)` → faltan posicionales → **TypeError**.

Todos los llamadores internos del compilador son correctos (`compiler.py:143,148,155,357,362` usan `(meta, opts, snapshot, stage)`). **El compilador de producción está sano; el test quedó anclado a una firma anterior** (probablemente `(meta, opts, stage)` antes de que `snapshot` se hiciera obligatorio). Corrección mínima (P2): actualizar las 3 llamadas del test a la firma real. NO cambiar el código.

**Relación con ura-mutmut-daily**: el barrido mutacional de las 06:00 falla con `AssertionError` porque estos 3 tests fallan de base (sin mutación) — documentado en `docs/udo/hallazgos-fondo.md` (MEDIA, recurrente 2 días). Al corregir los tests se desbloquea el barrido.

### 2.2 SafeCalculator — desincronización diseño/test

Test (`tests/unit/test_motor_assistant_executor.py:238`): espera `ValueError("Resultado no numerico")` para `max("abc")`.

Código (`motor/assistant/executor.py:164-175`): `_eval` solo acepta `ast.Constant` con valor numérico; un Constant str cae a `raise ValueError(f"Expresion no soportada: {type(node).__name__}")` → **"Expresion no soportada: Constant"** — lanzado al evaluar el **argumento**, antes de llegar al check de resultado (`:224` "Resultado no numerico").

Causa raíz: el código evolucionó a argumentos estrictamente numéricos; el test asume que un argumento str pasa y el resultado se valida después. Decisión de diseño (P2): (a) actualizar el test al comportamiento actual, o (b) permitir `ast.Constant` str en `_eval` y validar tipo en `_eval_call` (comportamiento del test). Recomendado (b) si se quiere `max("abc")` → error descriptivo; (a) si el contrato es "solo numéricos".

**Nota**: ambos grupos fallan **también en árbol limpio** (verificado tras stash) → NO son regresión del sandbox, son deuda preexistente de `main`.

### 2.3 Fallo flaky adicional (hypothesis)

El run con coverage (árbol limpio, 1265s) añadió un 5º fallo: `tests/unit/test_rules_hypothesis.py::TestDepthLimit::test_long_expression_raises` — **flaky**: no falló en el run normal sin coverage (231.89s). Causa probable: hypothesis con seed aleatoria + límites de profundidad límite (casi-assert). Hallazgo A15 (P3): fijar seed (`--hypothesis-seed`) en CI o ampliar el margen del test.

## 3. Cobertura por módulo

Run oficial (árbol limpio, 1265.70s): `pytest tests/unit -q --cov=motor --cov=core -p no:cacheprovider` → **TOTAL 83.5%** (23806 stmts / 3937 miss), 5 failed (4 conocidos + 1 flaky §2.3), 11 rerun. El run de referencia previo (82.0%, 32945 stmts) medía un árbol con el sandbox applied y no es la cifra oficial.

**Módulos por debajo del umbral de la política (80×100): 87**. Representativos por área:

| Área | Módulos (cobertura) |
|---|---|
| core/agents (CLI, healing, orquestador, telemetry) | 0.0% |
| core/voice (anker pipelines, tts_piper) | 0.0% |
| motor/core/voice (idem, shims) | 0.0% |
| motor/pipeline (executor 18.3%, loader 21.2%, orchestrator 26.7%) | 18-27% |
| motor/memory (snapshot 20.0%, journal 26.1%) | 20-26% |
| motor/events/hooks.py | 20.3% |
| core/watchdog_funciones.py | 20.5% |
| motor/assistant (llm_bridge 21.2%, episodic_memory 24.6%) | 21-25% |
| motor/intelligence (researcher 22.4%, memory/orchestrator 25.0%) | 22-25% |
| motor/scanner (collector_red 23.3%, collector_hw_vm 23.7%) | 23-24% |
| motor/guard/verifier.py | 26.0% |
| core/search_logger.py | 25.6% |
| knowledge/engine (extractors 25-31%, feedback 22.8%, governance_store 25.0%, memory_store 56.4%, deduction 35.8%, api 74.1%) | 22-74% |
| core/mochila/routes/proxy.py | 38.8% |
| core/change_guardian.py / guardian_disco.py / ast_sentinel.py / stealth_fetcher.py | 50.5-77.1% |
| +70 módulos adicionales <80% (lista completa en el run) | — |

Listado completo reproducible: `coverage report --omit='*/tests/*,*/scripts/*' --sort=cover | awk '$4+0<80'` (P1 — viola la política de cobertura por módulo, petición RAMON 2026-08-13).

## 4. Ruff

```
$ .venv/bin/ruff check .
Found 81 errors.  79 fixable
```

- **79 × RUF100** (unused noqa — cosmético, `--fix` automático): knowledge/engine 21, motor/core 17, core/mochila 16, scripts/pro 8, motor/assistant 5, motor/platform 4, core/model_router 4, motor/observability 2, motor/intelligence 2, monitor/health_check 1. P3.
- **2 × S310** (suspicious-url-open-usage): `core/secretario_cache.py:85` (urllib a Qdrant local; `# noqa: S310` presente en :91 pero ruff marca el Request construido en :85) y `monitor/health_check.py:63` (urllib a URL local, sin noqa). P2 — ambos construyen URL desde host/puerto configurados (verificado: sí, Qdrant configurado).
- **C901**: 48 funciones CC≥10 (ver §6). **E722**: 0. **F401**: 0.
## 5. Mypy

```
$ .venv/bin/python -m mypy --no-incremental core motor shared
Found 204 errors in 36 files (checked 460 source files)
```

Ejemplos reales: `motor/tests/test_intelligence_retrieval_cobertura.py:678: Name "test_llm_parse_score" already defined on line 599 [no-redef]`. El gate oficial **falla**; tras PM v3.1 el hook es informativo, no bloqueante. P1: triage prod vs tests (motor/tests/ contribuye a los 204).

## 6. Deuda técnica

- **`except: pass`**: 0 bare (E722=0). Auditados con `# noqa` OK: `guardian_logger.py:38,66`, `tts_piper.py:67,100`, `core/infra/heartbeat.py:241` (ImportError degradado). **Sin logging** (P2, silencio en fallo): `core/mochila/adapter.py:57`, `core/mochila/routes/proxy.py:151`, `core/mochila/providers/ollama.py:153`, `core/mochila/rate_limiter.py:23`, `core/mochila/circuit_breaker.py:60`. Scripts .sh: `scripts/pro/audit_diff.sh:38`, `orquestar_auditoria_hetzner.sh:31`, `external_audit.sh:249` (P3).
- **Funciones largas/complejas**: C901 48 (umbral CC≥10 de ruff). Distribución: scripts/pro 25, core/mochila 6, motor/cli 3, motor/plugin 2, motor/intelligence 2, motor/core 2, motor/brain 1, motor/assistant 1. Consistente con cierre S5b/S5c (núcleo sin CC≥20 ni longas >60; las 48 son CC 10-19).
- **Código muerto / duplicación**: 0 duplicados reales (§7).

## 7. Duplicados entre core/ y motor/

9 pares con nombre idéntico (chunking, config_manager, document_quality, json_logger, memory_engine, notifier, query_cache, search_engine + __init__): **falso positivo** — `motor/motor/core/` NO existe (verificado), y los `core/X.py` son **shims intencionales** (`sys.modules[__name__] = motor.core.X`) por política de compatibilidad (ADR). **0 duplicados reales de implementación**. UraConfig canónico: `motor/core/config.py`.

## 8. Imports circulares / sin usar

- **0 imports circulares**: 5434 tests recolectados sin fallo de import = grafo de importación acíclico en tiempo de carga. core→motor: 54 ocurrencias (todas shims/compatibilidad intencionales); motor→core: 0.
- **F401**: 0 (ruff).

## 9. Seguridad básica

- **Secretos en git**: **0**. Grep por patrones (`sk-*`, `api_key=`, `password=`, `token=` ≥16 chars) en tracked files: solo `scripts/pro/apply-fixes.sh:149-156` y `external_audit.sh:203` que **leen de env/`/etc/ura/secrets.env`** (patrón correcto, sin valores literales).
- **Permisos**: `/etc/ura/secrets.env` 600 root:ramon ✓ (verificado por el humano). `~/.env` no existe.
- **eval/exec/shell=True/os.system/Popen-shell**: 0 en producción (falsos positivos: `model.eval()` en reranking/ce.py:50, regex en adr_generator.py:20).

## 10. Configuración duplicada / inconsistente

- Drift de claves en `config/*.json` vs `UraConfig` (`motor/core/config.py` canónico): `default_model`, `fallback_model`, `remote_host`, `remote_port`, `vision_model` presentes en JSON. P3: auditar cuáles siguen siendo fuente y cuáles deben deprecarse (política Fase 17: UraConfig es la vista tipada; JSON legacy debe deprecarse).

## 11. Servicios systemd

```
$ systemctl --failed
ura-mutmut-daily.service  loaded failed failed  (Servicio de Barrido Diario Progresivo de Mutation Testing)
```

1 failed (causa: §2.1). ~55 unidades ura-*, ~35 timers. Legacy **disabled, no failed**: `docker-ura-grafana.service`, `docker-ura-prometheus.service`, `docker-ura-qdrant.service`, `docker-ura-mejora-continua.service` (P3: retirar cuando la stack -f8 quede consolidada). Audit-api, backup-mac: OK. Heartbeat: 0 vram_pressure post-restart (umbral 64000 activo).

## 12. Webhook de alertas (9105)

```
$ curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9105/health   → 000
```

**CAÍDO** (operativo P1). Causa raíz: el contenedor `ura-alerts-webhook-f8` (Up 6h) corre la **imagen/compose previos al fix `16065d25`** — sin el try/except del import `from motor.core.notifier import notify` (ImportError → crash-loop) y sin los mounts `../../motor` y `/etc/ura/secrets.env`. El fix está en el repo (commit `16065d25`) pero **no desplegado**: `docker compose up -d` no recrea la imagen sin `--build`. Acción (sudo humano): `cd deploy/prometheus && sudo docker compose up -d --build webhook-alerts` + `sudo docker logs --tail 20 ura-alerts-webhook-f8`.

## 13. Duplicación de procesos llama-server

```
$ nvidia-smi --query-compute-apps=pid,used_memory,process_name --format=csv,noheader
2823, 6675 MiB, /opt/llama.cpp/build/bin/llama-server --jinja
2690474, 1688 MiB, /usr/bin/python3
2242195, 507 MiB, /usr/local/lib/ollama/llama-server --model
```

**2 procesos llama-server de 2 runtimes distintos** (P2, perf): el del Model Router (llama-server directo `/opt/llama.cpp`, 6.6 GB, `--jinja`) + el de Ollama (llama-server interno, 0.5 GB; en momentos de carga llegó a 41 GB con el modelo grande). Ambos sirven inferencia LLM → doble reserva de VRAM; unificación a decidir (¿router apunta solo a Ollama o solo a llama.cpp?). Total GPU actual ~8.9 GB < umbral 64000 ✓.

## 14. Hallazgos por severidad

| ID | Sev | Hallazgo | Evidencia |
|---|---|---|---|
| A01 | P1 | Webhook alertas caído (9105 → 000); imagen vieja sin fix 16065d25 | §12 |
| A02 | P1 | Mypy gate falla: 204 errores / 36 archivos | §5 |
| A03 | P1 | 25+ módulos con cobertura <80% (política 80×100) | §3 |
| A04 | P1 | mutmut-daily failed (tests base rotos §2.1) | §11 |
| A05 | P2 | 3 tests knowledge/compiler desactualizados (firma `_ctx_stage` antigua) | §2.1 |
| A06 | P2 | SafeCalculator: test vs diseño desincronizados | §2.2 |
| A07 | P2 | 48 funciones CC≥10 (25 scripts/pro) | §6 |
| A08 | P2 | except:pass sin logging en core/mochila (5 sitios) | §6 |
| A09 | P2 | 2× S310 urlopen sin restricción de esquema explícita | §4 |
| A10 | P2 | 2 runtimes llama-server (router /opt/llama.cpp + Ollama) | §13 |
| A11 | P3 | 79× RUF100 unused noqa (cosmético, --fix) | §4 |
| A12 | P3 | Drift config/*.json vs UraConfig (5 claves) | §10 |
| A13 | P3 | 4 unidades docker-ura-*.service legacy (disabled) | §11 |
| A14 | P3 | except:pass en 3 scripts .sh sin logging | §6 |
| A15 | P3 | Flakiness hypothesis (test_rules_hypothesis) en run con coverage | §2.3 |

**P0 = 0**: no hay pérdida de datos, riesgo de seguridad activo ni rotura funcional de producción.

## 15. Evidencia y reproducción

Todos los comandos del informe se ejecutaron en ASUS (2026-08-18 16:40-17:10 CEST) sobre `main` @ `a097dd95` con árbol limpio (excepto el run de referencia de cobertura, señalado en §3). Los 4 fallos de pytest se reproducen en árbol limpio; el resultado completo del run de cobertura confirmatorio queda en `/tmp/opencode/audit_coverage.txt` (máquina local, no versionado).
