# PLAN DE EJECUCIÓN ARQUITECTURA URA v4.0

**Fecha:** 2026-08-06
**Estado:** Plan detallado — aprobado para ejecución
**Ejecutor:** Agente Tester (ASUS)
**Alcance:** TODAS las fases EXCEPTO Fase 2 (providers LLM → Ramón + otro agente)
**Regla de oro:** si dudas, archivar a `.attic/` con `git mv` (nunca eliminar directo). Cada fase termina con commit + `make validate`.

---

## CONTEXTO REAL VERIFICADO (4 auditorías read-only, 2026-08-06)

### Hallazgos que CORRIGEN el plan original

| Hallazgo | Impacto en el plan |
|---|---|
| **`ura-mochila.service` está ACTIVO en producción** (`core/mochila/mochila_server.py`, puerto 4098) | **core/mochila/ y core/memoria/ son VIVOS**, NO muertos. F3/F5 se reducen a auditar/documentar, NO eliminar |
| **Memoria v2 NO está en `motor/core/memoria/`** (no existe) sino en `motor/memory/` + `motor/intelligence/memory/` | Fase 3 canónico = `motor/memory` + `motor/intelligence/memory`, NO `core/memoria` que está VIVO |
| 1381 tests pasan, ~116 referencian core/ | `core/` tiene cobertura real de tests → proteger |
| Purga 2026-08-05 (commit `38b7921c`) archivó 101 herramientas y dejó **~25 referencias rotas** en código vivo | Fase 6 requiere REPARAR ro s antes de archivar más |
| 5 servicios systemd FAILED reales: `ura-consolidate`, `ura-fix`, `ura-hetzner-tunnel`, `ura-openclaw`, `ura-voice` | Fase 7 solo es DIAGNÓSTICO + documento (Ramón ejecuta systemctl) |
| `deploy/opencode.service` contiene **secretos hardcodeados** | Fase 7 debe marcar para saneo |
| 3 timers del plan no existen: `tuneladora-mantenimiento.timer`, `ura-auto-reindex.timer` ya purgados; `ura-mutmut.*` sin integrar en manage_timers | Fase 7 documenta, integra ura-mutmut en manage_timers |

### Clasificación verificada v4.0

| Etiqueta | Componentes |
|---|---|
| 🟢 CANÓNICO/VIVO | `core/mochila/*` (PROD :4098), `core/memoria/*` (PROD), `motor/core/llm/*`, `motor/memory/*`, `motor/intelligence/memory/*`, `scripts/pro/tuneladora/*` (Makefile+tests), CLI (30 scripts+ tests) |
| 🟡 TRANSICIÓN | `core/model_router/` (servicio user inactive, 8 tests pasan), `scripts/pro/auto_reglas.py`+`reglas_loader.py` (imports rotos), `scripts/pro/consolidacion.py` (imports autonomy rotos → ura-consolidate FAILED), `scripts/pro/dashboard.py` (goal_manager archivado → Makefile dashboard roto) |
| 🔴 MUERTO | `core/sandbox.py` (0 importadores, su propio test lo declara muerto), `deploy/ia-flujo.service` (ejecuta `app/` archivado), `deploy/ura-mcp.service` (ejecuta `mcp_mochila.py` archivado — no está instalada), `ura-mutmut.*` (fuera de manage_timers y systemd) |

---

## FASE 0 — Preparación

**Objetivo:** Backup + mapas + etiquetado. Sin tocar código.

| # | Acción | Comando / Método | Estado |
|---|---|---|---|
| 0.1 | Backup completo (tag) | `git tag -a pre-arch-v4.0` (local, sin push) | 🔜 |
| 0.2 | Mapa de imports core | `pydeps core/ --show-deps > docs/arch_core_deps.svg` | 🔜 |
| 0.3 | Mapa de imports motor | `pydeps motor/ --show-deps > docs/arch_motor_deps.svg` | 🔜 |
| 0.4 | Etiquetar paquetes clave | Añadir docstring de etiqueta en `__init__.py` de core/mochila, core/memoria, motor/core/llm, motor/memory (SIN cambiar imports) | 🔜 |
| 0.5 | Este documento plan | `docs/ARQUITECTURA_v4.0_PLAN.md` | ✅ este |

**Pendiente claro al final:** push del tag (requiere decisión sobre origin/main 478 atrás)

---

## FASE 1 — Limpieza superficial (ya residual cerrada)

Sub-fases previas de 2026-08-05: `.bak=0`, `data/`+`mutants/` en .gitignore, 108 __pycache__ limpiados, `tools/benchmarks/`→`.attic/`, `benchmark_ke.py` archivado, `cli.py` restaurado.

**Pendiente residual:** volver a limpiar `__pycache__` regenerados al final de TODAS las fases (paso final es documental).

---

## FASE 3 — Unificación de Memoria (adaptada a realidad)

**CORRECCIÓN DE PLAN:** `core/memoria/` es VIVO (servidor :4098 lo importa: analizador/consulta/ingesto/rastreadores/sintetizador/vigilante). NO se elimina.

| # | Acción | Detalle | Pasa |
|---|---|---|---|
| 3.1 | Documentar arquitectura de memoria real | `docs/ARQUITECTURA_v4.0_DIAGNOSTICO.md` tabla memoria: 3 vías (core/memoria VIVO, motor/memory V2, motor/intelligence/memory V12) | ✅ |
| 3.2 | Verificar si existe `scripts/pro/memoria.py` | NO existe (verificado) — documentar | ✅ |
| 3.3 | Auditar `scripts/pro/conciencia.py` | VIVO indirecto (pipeline_supremo exec); no archivar. Documentado | ✅ |
| 3.4 | Archivar rótulos sueltos muertos | `memoria_fallos.py`, `memoria_movimiento.py` (raíz) — verificar imports antes | 🔜 |
| 3.5 | PENDIENTE v4.0e: unificación real de memoria | Migrar core/memoria→motor + puente. **Requiere tocar motor/core → Ramón** | ⏳ Pendiente |

**Dejar pendiente al cierre:** la unificación real (v1→v2) es de apertura de motor → documentada como pendiente en fase.

---

## FASE 4 — Unificación de Pipeline

**La pesquisa del plan estimaba 3 pipelines muertos; la auditoría confirma:**

| Script | Real | Veredicto |
|---|---|---|
| `scripts/pro/tuneladora_pipeline.py` | **NO EXISTE** | — |
| `scripts/pro/pipeline_refactor.py` | Existe, invocada por `tuneladora_mejora.py:114` | **VIVO** (canónico) |
| `scripts/pro/pipeline_supremo.py` | Existe, invocada por `core/ingestador_red.py:122` | **VIVO** (canónico) |
| `scripts/pro/tuneladora/pipeline/` | Ya archivado en F1.3 | — |

| # | Acción | Detalle |
|---|---|---|
| 4.1 | Crear `docs/PIPELINE.md` | Doc el pipeline canónico (tuneladora/ + sus conexores external) |
| 4.2 | Verificar referencias de pipeline_supremo a archivados | `pipeline_supremo.py` invoca `token_screen`, `scanner_autoajuste`, `inspectores`, `openclaw_reviewer` (archivados) → comprobar si degradan con error o fallan | 🔜 |
| 4.3 | Reparar referencias rotas a archivados | En `tuneladora_mantenimiento.py` (11 refs a archivados) — evaluar: degradarlos con captura de error o documentar fallback | 🔜 |

**Cuidado especial:** NO tocar `scripts/pro/tuneladora/*` (regla Ramón). `tuneladora_mantenimiento.py` es la raíz de la tuneladora, también protegida.

---

## FASE 5 — Unificación de Routers (adaptada)

**IGUAL QUE F3:** `core/mochila/router.py` es VIVO (sic.). Lo CANÓNICO es doble: un v1 en prod, un v2 en motor.

| # | Acción | Detalle |
|---|---|---|
| 5.1 | Documentar triplicación de routers | cada veredicto verificado (v1 mochila VIVO PROD; v2 motor/core/llm/router VIVO; core/model_router/ MUERTO en repo, 8 tests — pero model-router servição tal activo desp de /home/ramon/URA/core/model_router.py AU3) | ✅ |
| 5.2 | Archivar `core/model_router/` si se confirma MUERTO | Verificar que el despliegue real está fuera del repo (por AGENTS.md `/home/ramon/URA/core/model_router.py`). Si el paquete en repo no es invocado por nadie vivo, archivar | 🔜 |
| 5.3 | Nota AGENTS.md | AGENTS.md dice model-router activo :11435 — REAL inactive user + system unit roto → documentar | 🔜 |

---

## FASE 6 — Purga de herramientas

**Meta:** de 178 (el índio viejo) a algo razonable. Criterios REALES verificado:
- CONECTADA (crontab/timer/service/Makefile/hooks/CI/imports/tests) → CONSERVAR
- SIN CONEXIÓN → ARCHIVAR a `.attic/tools/`

### 6.1 — Archivar en bloque los SIN CONEXIÓN verificado
De la auditoría scripts/pro: aplicar-fixes.sh, audit_diff.sh, auto_export_context.sh, backup_unified.sh, backup_gx10_configs.sh, check_licenses.sh, response (`.sh`), conectar_servidor_externo.sh, conflict_detector.sh, daemon_procesamiento_lento.sh, detect_environment.sh, dr_test.sh, evolve.sh, external_audit.sh, false_positive_baseline.sh, filtro_cascada.sh, fix_sudo_run.sh, etc → **pero OJO**: hay cadenas internas (ej `watcher_auditoria.sh`→`auditoria_pesada.sh`, `fpfn_report.sh`→`fn_scanner`+`fp_scanner`). Si archivo un eslabón de una cadena SI CONEX ex, rompo el primario. → **Archivar por GRUPOS de cadena completa o no archivar.**

### 6.2 — Reparar referencias rotas a archivados (BLOQUEADO → pregunta Ramón)
- `tuneladora_mantenimiento.py` (11 pasos), `tuneladora/plugins/*` (5 refs), `pipeline_supremo.py` (6 refs), `consolidacion.py` (autonomy.learning — ura-FAIL), `dashboard.py` (goal_manager), `auto_reglas.py` (reglas_applier/generator), `motor/cli/cmd_ura.py:515` (arq_auditor), `ciclo_rapido.sh` (auto_conciencia), `deploy/ura-mcp.service` (mcp_mochila)
→ **Decisión:** restaurar los scripts archivados del núcleo tuneladora O eliminar los pasos O degradar con try/except. **Requiere decisión de Ramón** (código core tuneladora).

### 6.3 — Regenerar TOOLS_INDEX
El generador está archivado (`.attic/tools/scripts_pro/tools_index.py`). Re-archivar, regenerar manual modulis actualizado.

---

## FASE 7 — Servicios systemd (SOLO DIAGNÓSTICO + PLAN para Ramón)

**Datos recogidos en auditoría 3 (verificado LIVE):**

| Servicio | Estado real | Causa | Acción (Ramón) |
|---|---|---|---|
| ura-consolidate | ❌ failed | autonomy.learning imports rotos en consolidacion.py | restaurar autonomy O dañar pasos |
| ura-fix | ❌ failed | sanear_codigo.py? verificar | diagn|
| ura-hetzner-tunnel | ❌ failed | ssh tunnel | sudo fix |
| ura-openclaw | ❌ failed | node openclaw gateway (env?) | sudo fix |
| ura-voice | ❌ failed | `demo_pipeline_voz.py` MISSING (fuera `build/lib`) | sudo fix |
| ura-mutmut.* | ⏳ no instalado | no está en manage_timers+no en systemd | integrar o archivar |
| `deploy/opencode.service` | ⚠️ no instalada | **SECRETOS hardcodeados** | sanear |

**Entregable:** `docs/ARQUITECTURA_v4.0_DIAGNOSTICO.md` tabla actualizada + documento `docs/SYSTEMD_V4.0.md` con plan de comandos EXACTOS para Ramón.

**Delega claro:** todo systemctl → Ramón. Yo solo documento + corrijo archivos repo (units en deploy/ que apunten a scripts que no existen → marcar o limpiar).

---

## FASE 8 — Documentación y validación

| # | Documento | Estado |
|---|---|---|
| 8.1 | `docs/ARQUITECTURA.md` (v4) | 🔜 crear |
| 8.2 | `docs/MODULOS_CANONICOS.md` | 🔜 crear |
| 8.3 | `docs/DEPRECADO.md` | 🔜 crear |
| 8.4 | `docs/TOOLS_INDEX.md` | 🔜 regenerar (ver F6.3) |
| 8.5 | `docs/SERVICIOS.md` | 🔜 crear (tabla LIVE) |

**Validación final:**
1. `make validate` ✅
2. `git status` limpio
3. Tag `v4.0.0-arch` (decisión Ramón)
4. `docs/BACKLOG.md` actualizat

---

## ORDEN DE EJECUCIÓN

F0 → F1 (verificación residual) → F6.1 (purga segura bloque por bloque) → F4 → F5 → F3 → F7 (docs) → F8 → cleanups → cierre

**Por cada fase:** commit `tipo(scope): descripción` (solo archivos intendidos), `make validate`, git status limpio, 0 regresiones (1381 tests baseline).

## RIESGOS Y MITIGACIONES

| Riesgo | Mitigación |
|---|---|
| Eliminar algo usado | ctx.md 7.5 git mv a .attic/, volumen git puede la purga |
| Romper validate | cada fase commite separado; make validate verifica |
| cadena .sh interna | auditar cadena completa antes de archivar |
| tola core/mochila PROD | NUNCA tocar 4098; solo documentar |
| El despice de refs rotas requiere decisión | BLOQUEADO hasta Ramón |
| Agente paralelo revierte | `git status` verificado antes/después; fix de timer ya raíz |

---

## PENDIENTES DE CIERRE (una por fase, se cierran KAA al final)

| Fase | Pendiente |
|---|---|
| F0 | Push/decición tag pre-arch (origin 482 atrás) |
| F1 | — |
| F3 | Unificación de memoria v1→v2 (requiere tocar motor/core → Ramón) |
| F4 | Decisiones deidad de refs pipeline/tuneladora rota |
| F5 | Archivo core/model_router (decisión: real Life fuera de repo?) |
| F6 | Repair refs rotas de purga (restaurar o degradar) — requerir Ramón |
| F7 | Todo systemd → Ramón (sudo, rootfs) |
| F8 | Tag final v4.0 + BACKLOG |