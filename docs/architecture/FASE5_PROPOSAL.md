# FASE 5 — Propuesta de Ejecución (Refactorización)

**Estado:** Propuesta v1.0 — 2026-08-01
**Objetivo:** Reducir funciones >60 líneas y complejidad ciclomática sin cambio de comportamiento observable.

## 1. Contexto y datos medidos (2026-08-01)

| Métrica | Valor |
|---------|-------|
| Funciones >60 líneas (producción) | **96** |
| Funciones con ciclomática >=20 | **8** |
| Tests CI-style verdes (Paso 0 F4) | 2511 (930 unit + 208 infra/knowledge/contracts + 1373 integration) |
| Cobertura baseline F4 (producción, omit policy) | core 16.0% - motor 60.9% - knowledge 58.4% - monitor 54.4% - mantenimiento 20.2% - raíz 81.9% - global 48.6% (33.677 stmts) |
| Módulos 0% con sospecha de dead code | 4 (mochila_server, ura_multi_agent, sandbox_orchestrator, auto_reindex) |

### Top funciones >60 líneas (96 total)
- 234 `knowledge/engine/cli/main.py:30 build_parser`
- 228 `knowledge/engine/knowledge_base.py:110 generate_knowledge_base` (cc 34)
- 178 `knowledge/engine/compiler.py:49 compile_source`
- 144 `knowledge/engine/extraction_service.py:257 _worker_loop`
- 129 `motor/diagnostico/pattern_matcher.py:6 buscar_patrones`
- 128 `knowledge/engine/archiver.py:111 archive_source`
- 127 `motor/assistant/api/routes.py:57 chat` (zona otra entidad)
- 123 `monitor/snc.py:252 poll_services` (cc 23)
- 123 `knowledge/engine/validator.py:53 validate_knowledge_object` (cc 21)
- 118 `motor/intelligence/agents/reflection.py:139 _reflect`
- 108 `mantenimiento/ura_maintenance_remote.py:106 run_remote_maintenance`
- 96 `core/memory_engine.py:101 index_documents`
- 88 `core/model_router/handler.py:296 do_POST` (ya con 26 tests F4)
- 86 `motor/assistant/conversation.py:179 process_user_message` (zona otra entidad)
- 84 `core/mochila/mochila_server.py:446 v1_chat_completions` -> dead code (ver M1)
- ... (96 en total; inventario completo regenerable con script en data/baseline/)

### Top ciclomática >=20 (8 total)
34 `generate_knowledge_base` - 27 `cmd_doctor` - 23 `poll_services` - 22 `cmd_audit` - 21 `validate_span_tree` - 21 `validate_knowledge_object` - 20 `cmd_learn` - 20 `cmd_rules_eval`

## 2. Conflictos identificados (C1-C10) y mitigaciones

### C1 - F5 vs F4 Cobertura: los objetivos de F5 son los módulos menos probados
Los >60 líneas viven exactamente en los módulos 0-20% de cobertura. Refactorizar sin red viola ADR-007/R7.
**Mitigación:** intercalado por módulo: (1) test de seguridad mínimo -> (2) refactor -> (3) verificación.
Los 9 módulos ya cubiertos por F4 (ura_maintenance, handler, dashboard, exporter, deduplication, schema_org, llm_base, health_check, assistant_metrics) pueden refactorizarse YA en Sprint 5b.

### C2 - ADR-007 (Regla del Núcleo): core/ exige ADR por cambio
**Mitigación:** ADR-005-F5 (plantilla por lote homogéneo, un commit = un ADR), semantic freezing (comportamiento observable idéntico, validado por tests existentes), degradación documentada.

### C3 - R7: no refactor sin ADR + commit separado
**Mitigación:** 96 funciones agrupadas en ~15-20 commits, cada uno con ADR propio y mensaje <=100 chars. Nunca mezclar refactor con fixes de bugs en el mismo commit (los bugs documentados en tests F4 se corrigen tras el refactor en commit aparte).

### C4 - Otra entidad activa en motor/assistant y motor/cli
`routes.py chat`, `conversation.py`, `cmd_ura.py cmd_audit`, `cmd_diag.py cmd_learn` están en zona de colisión.
**Mitigación:** check `git status --short <file>` + `git log -1 -- <file>` antes de tocar; si la otra entidad lo modificó en las últimas 48h -> posponer a Sprint 5e (revisar de nuevo). Nunca refactorizar ficheros con working-tree sucio.

### C5 - Hooks de pre-commit estrictos
pre-commit corre ruff+mypy+bandit+semgrep+pytest(core+monitor+motor) y el post-commit genera ADR automático.
**Mitigación:** cada commit F5 pasa el hook completo (nunca --no-verify); usar PRE_COMMIT_HOME=/home/ramon/URA/.pre-commit-cache; verificación con suite chunks al cerrar cada sprint (8-10 min).

### C6 - Baseline de cobertura recién creado (coverage_f4.json, 4c68db1)
Un refactor que divide/une statements cambia numerador/denominador por paquete.
**Mitigación:** las extracciones puras preservan statements -> impacto ~0; re-medir al cierre de cada sprint; desviación >1pp documentada en el acta. Umbrales F4 (core 88%, motor 92%, knowledge 88%, resto 80%) se miden con `make coverage` (fail-under 85 global).

### C7 - Orden de fases (roadmap): F4 antes que F5
El roadmap ya prevé F4 (Cobertura) -> F5 (Refactorización). Correcto: F4 da la red de seguridad. No bloquear 4b/4c por F5: se intercala por módulo, priorizando primero los módulos ya probados.

### C8 - CLIs declarativos: refactor de valor bajo
`build_parser` (234 l), `cmd_doctor`, `cmd_audit`, `cmd_learn`, `cmd_rules_eval`: configuración declarativa, tests CLI excluidos de CI, alto riesgo de romper UX de consola con poco beneficio.
**Mitigación:** NO refactorizar en esta fase; documentar en acta como deuda aceptada (mismo tratamiento que `noqa: PLR0915`).

### C9 - Event loops con estado compartido
`_worker_loop` (144), `archiver` (128), `poll_services` (123): riesgo de races (locks/colas). F28 ya tiene bugs conocidos de concurrencia.
**Mitigación:** extraer SOLO el procesamiento de item como función pura (`_process_item`), sin tocar locks ni colas; no refactorizar `tracing_platform.validate_span_tree` (zona de bugs F28 conocidos).

### C10 - Deuda ya aceptada con noqa
`do_POST` tiene `# noqa: PLR0915` - deuda aceptada, pero AHORA tiene 26 tests.
**Mitigación:** refactor factible y seguro en Sprint 5b (extraer `_route_direct`, `_route_routed`, `_emit_response`).

## 3. Mejoras detectadas en el análisis (M1-M7)

- **M1 - Dead code audit (mayor ganancia):** `core/mochila/mochila_server.py` (486 stmts, 0%, única referencia = string en `status_endpoint.py:41` y `build/` obsoleto) -> borrar o archivar a `.attic/`. `core/ura_multi_agent.py` y `core/sandbox_orchestrator.py` solo referenciados por `scripts/pro/patch_timestamps.py` (scanner) -> auditar. `core/auto_reindex.py` solo por scripts de auditoría -> auditar. Borrar 4 módulos (~1.200 stmts de golpe elimina una parte enorme del gap de core).
- **M2 - build/ regenerado:** el grep encontró `build/lib/core/mochila/status_endpoint.py` — el dir que rompió mypy en F29 volvió a existir. Verificar y eliminar + confirmar .gitignore.
- **M3 - Baselines desactualizados:** `data/baseline/radon.txt` decía "0 funciones cc>=20" (real: 8) y `data/baseline/loc_heavy.txt` es de F0. Regenerar ambos con script reproducible y commit.
- **M4 - tests-ci-exclude.txt obsoleto:** referencia `tests/test_sda.py` y `tests/test_unit.py` (movidos a `tests/legacy/`) y `tests/test_integration.py`, `test_openclaw.py`, `test_mochila.py` (ya no existen en raíz). Actualizar la lista.
- **M5 - Patrón de extracción:** usar prefijos `_build_*`, `_compute_*`, `_render_*` (convención existente en el repo) y submódulos ya creados (`core/mochila/`, `knowledge/engine/`). Prohibido crear helpers genéricos compartidos.
- **M6 - Shadowing de submódulos en `core/model_router/__init__.py`:** `metrics` y `vram_guard` sombrean sus submódulos y causan bugs sutiles en tests (documentado en tests F4 con `_patch_metrics`). Corregir en F5 (rename del attr o import absoluto) con ADR propio.
- **M7 - Bugfixes ya documentados en tests F4:** `is_safe_to_delete` (lstat fuera del try) y `freed=0` en `clean_old_logs`/`clean_temp_files` de `ura_maintenance.py` se corrigen en F5 (commit separado del refactor, con ADR).

## 4. Plan de ejecución (sprints)

### Sprint 5a - Preparación y auditoría (1-2h)
- A1: Dead code audit M1 -> decidir borrar/archivar (precedente F3-B2: agent_hierarchy.py) y ejecutar M2, M3, M4
- A2: Script reproducible de inventario (longitud + ciclomática) en `scripts/pro/` y commit de baselines regenerados
- A3: ADR-005-F5 (plantilla por archivo/lote) + registro de excepciones C8

### Sprint 5b - Refactor con red de tests YA existente (F4)
- `ura_maintenance.py`: extraer `_calcular_tamano_total`, `_cleanup_por_glob` + fix bugs M7 (commits separados)
- `handler.py do_POST`: extraer `_route_direct`, `_route_routed`, `_emit_response` (26 tests de red)
- `dashboard.py`, `exporter.py`, `deduplication.py`, `schema_org.py`, `llm_base.py`, `health_check.py`, `assistant_metrics.py`: extracciones puras (tests existentes como oráculo)
- Criterio: un commit por fichero, ADR por lote, suite `tests/unit` (930 tests, 2.5 min) tras cada commit

### Sprint 5c - Refactor con tests de seguridad nuevos (test-first)
- `knowledge/engine/knowledge_base.py generate_knowledge_base` (cc 34, 228 l): tests de seguridad -> extraer `_extraer_entidades`, `_construir_grafo`, `_guardar`
- `knowledge/engine/validator.py` (cc 21), `compiler.py` (178 l), `archiver.py` (128 l)
- `monitor/snc.py poll_services` (cc 23): extraer `_poll_service`, `_render_status`
- `motor/core/llm`: `validate_provider` (92 l), `finish_operation` (84 l), `strategy.call_with_retry` (103 l)
- Patrón: test -> refactor -> verificar test + ruff + pre-commit

### Sprint 5d - Event loops y estado
- `extraction_service._worker_loop` (144 l), `reflection._reflect` (118 l), `pattern_matcher.buscar_patrones` (129 l)
- Extraer SOLO `_process_item`/`_clasificar_patron` puros; no tocar locks/colas
- Revisión de zona otra entidad: si motor/assistant sigue activo, los archivos de colisión pasan aquí o se postergan

### Sprint 5e - Exclusiones documentadas (no refactorizar)
- CLIs declarativos C8 (build_parser, cmd_doctor, cmd_audit, cmd_learn, cmd_rules_eval)
- `motor/assistant/api/routes.py`, `conversation.py` si la otra entidad sigue activa
- `tracing_platform.validate_span_tree` (bugs F28)
- `mochila_server.py` si no se borra en 5a (depende de auditoría)

### Sprint 5f - Validación final y cierre
- F.1: Suite completa chunks (2511 tests, 8-10 min) 0 regresiones
- F.2: `ruff check .` 0 errores nuevos (baseline 27)
- F.3: `make coverage` re-medida por paquete, sin regresión >1pp
- F.4: Inventario final: 96 -> <=29 funciones >60 líneas (>=70% reducción); 8 -> <=3 cc>=20
- F.5: Tabla comparativa baseline + acta `FASE5_CLOSEOUT.md` + tag `v0.x.0-fase5`
- F.6: `git status` limpio y sincronización ASUS/Mac

## 5. Criterios de aceptación (checklist)

| # | Criterio | Métrica |
|---|----------|---------|
| 1 | Reducción funciones >60 líneas | 96 -> <=29 |
| 2 | Reducción ciclomática >=20 | 8 -> <=3 |
| 3 | Tests CI-style | 2511 sin regresiones |
| 4 | Ruff | 0 errores nuevos |
| 5 | Cobertura por paquete | sin regresión >1pp |
| 6 | Commits | 1 commit = 1 refactor + ADR + mensaje <=100 chars |
| 7 | Dead code | 4 módulos auditados, decisión documentada |
| 8 | Semantic freezing | comportamiento observable idéntico (tests como oráculo) |

## 6. Riesgos

- **Alto:** refactor sin red en módulos 0% -> mitigado por M1 (dead code primero) + test-first en 5c
- **Medio:** colisión con otra entidad -> check git antes de tocar cada archivo (C4)
- **Medio:** regresión sutil de comportamiento -> semantic freezing + suite completa por sprint
- **Bajo:** hooks bloqueando -> PRE_COMMIT_HOME + nunca --no-verify

## 7. Dependencias

- F4 Sprint 4a cerrado (red de tests) - LISTO (2026-08-01)
- F4 4b/4c continúan en paralelo (no bloqueante, intercalado)
- Otra entidad: motor/assistant (revisión en 5d)
