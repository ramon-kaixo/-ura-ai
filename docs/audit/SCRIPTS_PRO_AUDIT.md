# SCRIPTS_PRO_AUDIT — Auditoría de scripts/pro/ (Fase 1.3)

**Fecha:** 2026-08-02
**Rama:** `main`
**Estado:** ✅ Auditado y clasificado

## Resumen

| Métrica | Valor |
|---------|-------|
| Archivos antes | 208 |
| Benchmarks movidos a `tools/benchmarks/` | 15 |
| Refactors huérfanos movidos a `.nervioso/descarte/` | 3 |
| Archivos `.bak` eliminados (no tracked) | 1 (`benchmark_qdrant.py.bak`) |
| Archivos después | 189 |
| Referencias a benchmarks desde CI/cron/tuneladora | 0 (verificado) |

## Acciones ejecutadas

### MOVER → `tools/benchmarks/` (15, sin referencias externas)
`benchmark_baseline.py`, `benchmark_compare_chunking.py`, `benchmark_f10_perf.py`,
`benchmark_f24.py`, `benchmark_f29_b2.py`, `benchmark_final_reranking.py`,
`benchmark_final_retrieval.py`, `benchmark_hybrid.py`, `benchmark_hybrid_refined.py`,
`benchmark_ke.py`, `benchmark_llm.py`, `benchmark_qdrant.py`, `benchmark_rag.py`,
`benchmark_rerank.py`, `benchmark_reranking.py`

- Verificación previa: 0 imports cruzados (`import benchmark_*`), 0 referencias en
  `.github/`, crontab, tuneladora_mantenimiento.py, tuneladora_mejora.py.
- Commits: `b31d7a6`, `88c4bf1`

### MOVER → `.nervioso/descarte/` (3, huérfanos)
- `refactor_large_functions.py` — superado por `refactor_large_functions_v2.py`
  (el único invocado por tuneladora, línea 207 de tuneladora_mantenimiento.py)
- `refactor_4_motores.py` — utilidad puntual, sin referencias
- `refactor_worker.py` — sin referencias

### ELIMINAR (1, no tracked)
- `benchmark_qdrant.py.bak` — backup local obsoleto, nunca en git

## Clasificación de los 189 restantes

| Categoría | Nº | Ejemplos |
|-----------|----|----------|
| Diagnóstico/Mantenimiento | 20 | inspectores.py, compactadora.py, scanner_autoajuste.py |
| Auditoría | 16 | auditoria.sh, quality_metrics.sh, fn_scanner.sh |
| Red/Backup | 16 | backup_unified.sh, gx10_sync.sh, safe_rollback.sh |
| Utilidades | 12 | utils.py, check_secrets.py, ura-query.py |
| Instalación/Deploy | 10 | instalar_gx10_circuit.sh, mcp_config.sh |
| GPU/Sistema | 10 | gpu_health.py, lock_manager.py, health_check.sh |
| Hetzner | 10 | deploy_to_hetzner.sh, rescue_hetzner.sh |
| Tuneladora/Pipeline | 10 | tuneladora_mantenimiento.py, tuneladora_mejora.py |
| RPA/Cámaras | 9 | rpa_linksys_v2.py, desplegar_dahua_supervisor.sh |
| Evolución/Ciclo | 8 | evolve.sh, filtro_cascada.sh |
| Config/Templates | 10 | tailscale-acls.json, gx10-api.service |
| Ejecución/Servicios | 5 | ejecutor_api.py, plugin_registry.py |
| Refactor (vivos) | 3 | refactor_large_functions_v2.py, refactor_v2.py |
| Router | 4 | pareto_router.py, router_rate_limiter.py |
| Sandbox | 4 | sandbox_industrial.py, jaulas_recursos.sh |
| Conciencia/Memoria | 4 | conciencia.py, ura_self_modify.py |
| OpenClaw | 4 | openclaw_reviewer.py, alineador.py |
| Voz/Visión | 3 | seed_correcciones_voz.py, supervisor_ciclo.sh |
| OTROS (sin clasificar) | 31 | adr_generator.py, ajustar_contexto.py, README.md, __pycache__ |

## Pendientes para Fase 3 (refactorizar si se mantienen)

Funciones CC≥20 detectadas por radon (ver inventario radon post-S5b):

| Archivo | Función | CC |
|---------|---------|-----|
| `scripts/pro/audit_secrets.py` | `main` | 32 |
| `scripts/pro/mcp_mochila.py` | `run_benchmark` | 37 |
| `scripts/pro/inspectores.py` | `anclaje_cromatico` | 28 |
| `scripts/pro/poda_mecanica.py` | `main` | 23 |
| `scripts/pro/dashboard.py` | `_handle_tools_call` | 21 |
| `scripts/pro/bypass_linksys_gui.py` | `main` | 24 |
| `scripts/pro/reglas_applier.py` | `cmd_audit` | 22 |
| `scripts/pro/autonomy/autonomy.py` | `main` | 22 |
| `scripts/pro/autonomy/learning/pattern_analyzer.py` | `analyze` | 32 |
| `scripts/pro/tuneladora/pipeline/runner.py` | `phase_integrity` | 24 |
| `scripts/pro/generate_arch_diagram.py` | `main` | 24 |
| `scripts/pro/tuneladora/shadow/layer3_shadow.py` | `check_f821` | 24 |

> Nota: estos scripts no forman parte del núcleo productivo (core/motor/knowledge/
> agents ya están a 0 CC≥20). La refactorización es opcional y de baja prioridad.

## Verificación reproducible

```bash
# Benchmarks accesibles en nueva ubicación
ls tools/benchmarks/ | wc -l          # 15
# Sin referencias rotas
grep -rn "scripts/pro/benchmark" .github/ scripts/pro/tuneladora_mantenimiento.py | wc -l  # 0
# Refactors huérfanos descartados
ls .nervioso/descarte/refactor_*.py | wc -l  # 3
```
