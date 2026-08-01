# REFACTOR_S5b — Acta de Cierre Sprint 5b (Refactor de Deuda de Complejidad)

**Fecha:** 2026-08-02
**Rama:** `main`
**Tipo:** Acta de cierre de sprint (T6 del plan `docs/architecture/FASE5_PROPOSAL.md`)

## Resumen

Sprint de refactorización sobre `main` de funciones con **LOC > 60** y/o
**CC >= 20** (radón sobre árbol AST propio), exclusivamente sobre funciones con
**red de tests** como oráculo, en commits atómicos de 1 función con ADR por lote.

| Métrica | Pre-F5 | Post-S5a | Post-5b | Delta 5b |
|---------|--------|----------|---------|----------|
| Funciones LOC > 60 | 96 | 94 | **85** | **-9** |
| Funciones CC >= 20 | 14 | 13 | **8** | **-5** |
| Archivos analizados | — | — | 484 | — |
| Funciones totales | — | — | 3.143 | — |

Inventario reproducible: `scripts/pro/inventario_f5.py` (flags `--json OUT`,
`--write`). Fórmula CC: `edges = 1 + If/While/For/ExceptHandler/With/Assert +
(BoolOp len-1); CC = edges - 1 + 2`.

## Funciones refactorizadas (13) + bugfix de seguridad (1)

### Lote A — ADR: `docs/architecture/ADR-005-F5-lote-A.md`

| # | Función | Cambio | LOC/CC | Commit | Oráculo |
|---|---------|--------|--------|--------|---------|
| 1 | `core/model_router/handler.py:296 do_POST` | orquestador + `_leer_body_json`, `_registrar_contexto`, `_clasificar_peticion`, `_servir_cache`, `_rutear_proxy`, `_emitir_respuesta` | CC 24→3 | `6143895` | test_router_handler (26) |
| 2 | `motor/core/llm/base.py:79 validate_provider` | 7 validadores | CC 20→3 | `ff63b14` | test_llm_base (20) |
| 3 | `knowledge/engine/validator.py:53 validate_knowledge_object` | `_validar_doc_type`, `_validar_warnings_core`, `_validar_tags_aliases`, `_validar_campos_obsoletos` | CC 21→2 | `ed6cbc2` | nightly (172) |
| 4 | `monitor/snc.py:252 poll_services` | `_state_inicial`, `_poll_mac_reachability`, `_check_only_if`, `_poll_servicio`, `_gestionar_openclaw`, `_state_final` | CC 21→3 | `e80cc86` | test_snc_poll_services (3) |
| 5 | `knowledge/engine/extraction_service.py:257 _worker_loop` | `_claim_next_job`, `_claim_next_job_fallback`, `_process_item` | C9 | `7ece6ca` | test_fase7 (48) |

### Bugfix de seguridad (M7) — ADR: `docs/architecture/ADR-005-F5-fix-seguridad-poll_services.md`

| # | Función | Cambio | Commit | Oráculo |
|---|---------|--------|--------|---------|
| 6 | `monitor/snc.py check_service` | **Vulnerabilidad**: `check_service` ignoraba `forbidden_commands` (solo `repair_service` filtraba) → un runbook malicioso podía ejecutar comandos arbitrarios (`rm -rf`). Fix: `check_service(check_cmd, forbidden=None)` retorna `False` si el comando está prohibido; `poll_services` pasa la lista del runbook. Descubierto por test-first C1. | `05ad0dc` | 3 tests nuevos en `tests/unit/test_snc_poll_services.py` (guardia permanente) |

### Lote B — ADR: `docs/architecture/ADR-005-F5-lote-B.md`

| # | Función | Cambio | LOC/CC | Commit | Oráculo |
|---|---------|--------|--------|--------|---------|
| 7 | `knowledge/engine/compiler.py:49 compile_source` | orquestador DAG por etapas + `_compilar_defaults`, `_ctx_stage` (elimina 4 duplicados), `_warnings_deletados`, `_etapa_parsing`, `_etapa_validacion`, `_sync_semantica`, `_auditar` | 178→24, CC 25→6 | `4c0f701` | nightly (172) |
| 8 | `knowledge/engine/parser.py:81 parse_source` | `_decodificar`, `_error_codigo` (unifica 5 errores), `_relaciones_extra` | 81→37 | `c670d1f` | nightly (172) |
| 9 | `knowledge/engine/validator.py:212 validate_batch` | `_construir_lookups`, `_validar_relaciones` (KE004), `_check_duplicados` (KE101/KE007) | 84→38 | `bfe342c` | nightly (172) |
| 10 | `knowledge/engine/migrations.py:111 migrate_db` | `_migrar_fresh`, `_validar_rango` (3 ValueErrors), `_aplicar_migracion` | 81→33 | `193e67a` | nightly (172) |
| 11 | `motor/intelligence/agents/reflection.py:139 _reflect` | `_resultado_reflexion` unifica 6 retornos duplicados | 118→57, CC 19→6 | `c3a3c92` | test_reflection (31) |
| 12 | `motor/core/evaluation/evaluator.py:100 evaluate` | `_validar_inputs` (tipado `EvaluationCorpus`), `_evaluar_query`, `_agregar`, `_latencia_stats` | 85→47 | `01e03e7` | evaluation + rules (18) |
| 13 | `motor/pipeline/executor.py:35 execute` | `_ejecutar_stages`, `_resultado_fin` (unifica 3 PipelineResult), `_anunciar_fallo` (unifica 2 publish FAILED) | 82→50 | `457a1e5` | test_observability_f11 (25) |
| 14 | `motor/plugin/registry_v2.py:160 _load_v2` | `_verificar_manifest`, `_verificar_compatibilidad`, `_cargar_dependencias`, `_cargar_modulo`, `_registrar_plugin` | 82→24, CC→6 | `6ac706d` | test_observability_f11 (25) |

## Validación

- **Hooks pre-commit verdes en los 14 commits** (semgrep wrapper, pytest, ruff-format).
- **mypy**: `motor/core/llm/base.py` 41 errores antes y después (sin regresión;
  el repo ya falla mypy globalmente — baseline aceptado).
- **Suites oráculo** de cada refactor: 100% verdes (recuentos en tabla).
- **Suite completa** (`pytest tests/ -q`): 1.940 passed, 49 skipped; único fallo
  `test_compile_returns_ok_when_no_changes` es **flaky dependiente del estado
  del corpus** (pasa aislado; falla si archivos de knowledge cambian durante la
  corrida de 7 min — la otra entidad modifica el repo en paralelo).
- Sin cambios de comportamiento observables (semantic freezing): refactors
  puramente extractivos con helpers privados.

## Excluidos de 5b (deuda documentada → 5c)

Requieren **test-first** (autorización) o quedan fuera de alcance:

- **Sin red de tests**: `generate_knowledge_base` (228/28, solo CLI),
  `ast_sentinel.analizar` (33), `parallel.execute` (21), `index_documents` (96),
  `healing.ejecutar` (84), `finish_operation` (84), `_chunk_section` (89),
  `call_with_retry` (103), `continuous.run` (95), `archiver.archive_source` (128),
  `pattern_matcher.buscar_patrones` (129), `guardian_openclaw.ejecutar` (89),
  `distribuir_tarea` (61), `_check_recursos` (73), `fetch_raw` (73),
  `run_remote_maintenance` (108), `comprimir_a_ideas` (74), `alerts.evaluate` (78).
- **C4 (prohibido)**: `executor._eval` (22), `routes.chat` (127), `cmd_memory` (76).
- **C8 (CLIs declarativos)**: `cmd_audit_db` (104), `cmd_ura` (76).
- **C9 (bugs F28)**: `validate_span_tree` (25).
- **Mochila (0% cobertura)**: `routes/proxy.py` x2 (23), `mochila_server.proxy_gateway` (23), `_stream_from_provider` x2.

## Lecciones aprendidas

1. **La red de tests asumida debe verificarse** (grep real en `tests/`): varias
   candidatas parecían cubiertas por suites homónimas (`test_hypothesis`,
   `test_tuneladora_auto_trigger`) que en realidad ejercitan otras funciones.
   Verificación sistemática: `grep -rn "<func>" tests/` antes de empezar.
2. **Test-first revela bugs reales** (M7): la política C1 se aplicó solo a
   `poll_services` y destapó una inyección de comandos vía runbook.
3. El pre-commit hace stash/restore automático del trabajo unstaged de la otra
   entidad activa en `main` — una edición se perdió una vez por interferencia
   (reaplicada); verificar `git status` antes de cada commit.

## Cierre

Sprint 5b cerrado: 13 refactors + 1 bugfix, 0 regresiones funcionales.
Deuda restante (8 CC>=20 y 85 longas) pasa al Sprint 5c con política test-first
por decisión del usuario por función.

- ADR Lote A: `docs/architecture/ADR-005-F5-lote-A.md`
- ADR Lote B: `docs/architecture/ADR-005-F5-lote-B.md`
- ADR Seguridad: `docs/architecture/ADR-005-F5-fix-seguridad-poll_services.md`
- Baselines: `data/baseline/radon.txt` (14 CC>=20), `data/baseline/loc_heavy.txt` (63.893 LOC)
