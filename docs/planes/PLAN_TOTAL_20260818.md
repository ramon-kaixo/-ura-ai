# PLAN TOTAL URA — 2026-08-18 (P0→P3)

- **TASK**: TASK-20260818-027 (auditoría) → deriva fases ejecutables
- **Base**: `main` @ `a097dd95` (árbol limpio; `stash@{0}` sandbox NO se toca)
- **Autor**: [WEB] · **Revisor propuesto**: [TERM]
- **Reglas transversales**: sin modificar código/config sin autorización de RAMON; no borrar archivos; no tocar modelos; no OpenCode local con Ollama; commits `tipo(scope): [TASK-ID][WEB] desc`; `git add` explícito (zona sandbox intocable); no tocar `docs/udo/coordination.json` (zona TERM/despertador).
- **Gates comunes a toda fase**: `ruff check .` 0 errores nuevos · `pytest -q --tb=short` sin regresiones (los 4 fallos conocidos se corrigen en P1.2) · cobertura ≥80% por módulo tocado (política 80×100) · `git status` limpio salvo el archivo ajeno de coordinación · revisión de TERM antes de DONE.

## P0 — Emergencias (0 ítems)

**No hay hallazgos P0** (sin pérdida de datos, sin riesgo de seguridad activo, sin rotura funcional en producción — ver auditoría §14). Esta fase queda como confirmación explícita y no se ejecuta.

## P1 — Operativo y gates (4 ítems)

### P1.1 Webhook alertas caído (A01) — responsable: RAMON (sudo) + WEB (verificación)
- **Qué**: desplegar el fix ya commiteado `16065d25` (import degradable + Dockerfile.webhook con httpx + mounts `../../motor` y `/etc/ura/secrets.env` ro).
- **Pasos (sudo humano)**:
  1. `cd /home/ramon/URA/ura_ia_1972/deploy/prometheus && sudo docker compose up -d --build webhook-alerts`
  2. `sudo docker ps --filter name=ura-alerts-webhook-f8`
  3. `sudo docker logs --tail 20 ura-alerts-webhook-f8`
- **Gate de cierre**: `curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:9105/health` → **200**; logs sin ImportError; `scripts/pro/verificar_instalaciones_f8.sh` → **9/9**.
- **Riesgo**: el rebuild de una imagen puede fallar por red/pip (httpx). **Rollback**: la imagen previa permanece taggeada; `sudo docker compose up -d` (sin `--build`) restaura el contenedor anterior. No afecta a 9094/3001/9095/9100.

### P1.2 Tests base rotos (A05, A06, A04) — responsable: WEB (ejecutor), TERM (revisor)
- **Archivos**: `tests/unit/test_knowledge_compiler_cobertura.py` (3 llamadas), `tests/unit/test_motor_assistant_executor.py:238` + `motor/assistant/executor.py` (según decisión).
- **Pasos**:
  1. `test_knowledge_compiler_cobertura.py`: cambiar las 3 llamadas de `_ctx_stage(meta, opts, stage, ...)` a la firma real `(meta, opts, snapshot, stage)` — test_snapshot (línea 451), test_errores_warnings, test_ctx_compatible (línea 709). **NO tocar `knowledge/engine/compiler.py`** (código sano, verificado).
  2. SafeCalculator: **decisión de RAMON** — (a) actualizar el test al comportamiento actual ("Expresion no soportada: Constant"), o (b) permitir `ast.Constant` str en `_eval` (executor.py:165) y validar tipo en `_eval_call` (executor.py:222-224) para obtener "Resultado no numerico". Recomendado (b) por coherencia con el contrato del test; (a) es más conservador (0 riesgo).
  3. Re-ejecutar los 2 archivos de test + suite completa.
- **Gate**: `pytest -q --tb=short` → **0 failed**; `ura-mutmut-daily.service` deja de fallar en el siguiente disparo (06:00) — verificar con `systemctl --failed`.
- **Riesgo**: bajo. **Rollback**: `git revert` del commit de tests.

### P1.3 Cobertura <80% (A03) — responsable: WEB (ejecutor), TERM (revisor)
- **Objetivo**: subir a ≥80% los módulos por debajo, priorizando APIs en producción.
- **Archivos objetivo (87 módulos <80% en run oficial; lista completa en auditoría §3)**. Orden de prioridad:
  1. `core/mochila/routes/proxy.py` (38.8%) y `knowledge/engine/api.py` (74.1%) — **APIs expuestas**, riesgo de regresión real.
  2. `core/search_logger.py` (25.6%), `core/watchdog_funciones.py` (20.5%), `core/change_guardian.py` (50.5%), `core/guardians/ast_sentinel.py` (77.1%), `core/guardian_disco.py` (71.3%), `core/stealth_fetcher.py` (72.6%) — núcleo de URA.
  3. `knowledge/engine/extractors/*` (25-31%), `feedback.py` (22.8%), `governance_store.py` (25.0%), `memory_store.py` (56.4%), `deduction.py` (35.8%).
- **Método**: tests por módulo (smoke + casos límite), ejecutar con `coverage run --rcfile` específico (política: rcfile propio sin `omit = scripts/*`), medir con `coverage report --sort=cover`.
- **Gate por módulo**: ≥80% medido con `coverage report --sort=cover | awk '$4+0<80'` → módulo ausente del listado.
- **Riesgo**: medio (tiempo). **Rollback**: los tests nuevos no alteran producción; si un test revela bug real, se registra hallazgo y se trata aparte.

### P1.4 Mypy gate (A02) — responsable: WEB, con triage primero
- **Pasos**: 1) triage de los 204 errores/36 archivos: separar producción vs `motor/tests/` (los tests de motor/ no deberían formar parte del gate de producción; decidir si se excluyen o se corrigen). 2) Corregir los errores de producción (no-redef, tipos). 3) Decidir el gate oficial (mantener informativo o hacerlo bloqueante en CI).
- **Gate**: `mypy --no-incremental core motor shared` → 0 errores en producción (tests de motor/ según decisión).
- **Riesgo**: medio (cambios de tipos). **Rollback**: `git revert`.

## P2 — Deuda de calidad (4 ítems)

### P2.1 except:pass sin logging en core/mochila (A08) — WEB
- **Archivos**: `core/mochila/adapter.py:57`, `core/mochila/routes/proxy.py:151`, `core/mochila/providers/ollama.py:153`, `core/mochila/rate_limiter.py:23`, `core/mochila/circuit_breaker.py:60`.
- **Pasos**: añadir `logger.warning/exception` (patrón existente de la mochila) manteniendo el comportamiento degradado. Verificar que no cambia el contrato (solo logging).
- **Gate**: ruff 0 nuevos + tests mochila OK + revisión de que el mensaje de log no expone secretos (no loguear headers/keys).

### P2.2 S310 (A09) — WEB
- **Archivos**: `core/secretario_cache.py:85` (noqa mover a la línea del Request o reestructurar), `monitor/health_check.py:63` (añadir noqa documentada + verificar que la URL es host/puerto configurados — verificado: sí).
- **Gate**: `ruff check --select S310 .` → 0 (o noqa justificada con comentario de seguridad).

### P2.3 C901 48 funciones (A07) — WEB, selectivo
- **Objetivo**: reducir complejidad donde haya riesgo de mantenimiento; **no** refactorizar en bloque. Prioridad: las 6 de `core/mochila` y las 4 de `motor/*` (núcleo); las 25 de scripts/pro se tratan aparte (herramientas, umbral de riesgo menor).
- **Método**: extracción de helpers siguiendo el patrón S5b/S5c (refactor + tests previos con cobertura del comportamiento).
- **Gate**: pytest sin regresiones; CC del módulo tocado no sube; 0 nuevas funciones >CC20.

### P2.4 Duplicación llama-server (A10) — RAMON (decisión) + WEB (ejecución)
- **Contexto**: PID 2823 `/opt/llama.cpp/build/bin/llama-server --jinja` (6.6 GB, Model Router) + PID 2242195 ollama llama-server (0.5-41 GB).
- **Decisión necesaria**: (a) router→Ollama exclusivo (apagar llama-server directo), (b) router→llama.cpp directo (Ollama solo para otros modelos), o (c) mantener dual documentado.
- **Ejecución tras decisión**: ajustar `motor/` (config de endpoints) + systemd del servicio afectado; verificar latencia y GPU (`nvidia-smi`).
- **Rollback**: restaurar config anterior (git revert + reinicio del servicio).

## P3 — Higiene (4 ítems)

### P3.1 RUF100 79 unused noqa (A11) — WEB
- `ruff check . --fix` → revisar diff (solo elimina directivas sobrantes) → commit. Gate: 0 errores RUF100, pytest sin regresiones.

### P3.2 Drift config/*.json vs UraConfig (A12) — WEB
- Auditar `default_model`, `fallback_model`, `remote_host`, `remote_port`, `vision_model` en `config/*.json`: quién los lee aún (grep de consumidores), deprecar los huérfanos (política Fase 17). Gate: `scripts/pro/audit_config.py` 0 problemas + consumidores verificados.

### P3.3 Unidades legacy docker-ura-*.service (A13) — RAMON (sudo) + WEB
- Tras consolidar la stack -f8 (P1.1 OK y 7 días sin incidentes): `sudo systemctl disable --now docker-ura-grafana.service docker-ura-prometheus.service docker-ura-qdrant.service docker-ura-mejora-continua.service` (los contenedores ura-grafana/ura-prometheus previos ya no deben arrancarse). Verificar con `systemctl is-enabled`.

### P3.4 Documentación y scripts .sh (A14 + docs) — WEB
- except:pass en `audit_diff.sh:38`, `orquestar_auditoria_hetzner.sh:31`, `external_audit.sh:249`: añadir log/echo del fallo.
- Actualizar: `docs/udo/hallazgos-fondo.md` (mutmut → asociado a A05 corregido), `docs/udo/PENDIENTES_SUDO.md` (estado tras P1.1), `docs/architecture/REFERENCIA_GX10.md` (nombres -f8, webhook 9105, llama-server dual), expediente TASK-20260818-026 (TERM, reporte mutmut).

## Dependencias y orden

```
P1.1 (webhook)      ── independiente ──► P3.3 (legacy) / P3.4 (docs)
P1.2 (tests)        ── desbloquea ──► A04 mutmut + CI + TASK-026 (TERM)
P1.3 (cobertura)    ── independiente (paralelizable por módulo)
P1.4 (mypy)         ── independiente
P2.x ── después de P1.2 (evita ruido de diff)
P3.x ── al final, todo cosmético
```

**Estimación**: P1.1 10 min (sudo) · P1.2 1-2 h · P1.3 8-16 h (16+ módulos) · P1.4 2-4 h · P2 4-6 h · P3 2-3 h.

## Cierre

Cada fase cierra con: commits con TASK-ID [WEB], revisión de TERM (APROBADO/CAMBIOS_SOLICITADOS), gates verdes y actualización de `docs/udo/` + `docs/architecture/METRICAS_BASELINE.md` si toca métricas. Sin aprobación del revisor no se declara DONE (protocolo ejecutor-revisor TASK-20260816-005).