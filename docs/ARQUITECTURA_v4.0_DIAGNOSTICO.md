# ARQUITECTURA v4.0 — Diagnóstico de Limpieza (Fase 1)

**Fecha:** 2026-08-06
**Estado:** Fase 1 residual COMPLETADA
**Autor:** Agente Tester (sesión ASUS)

## Objetivo

Clasificar el estado REAL de los componentes del repositorio (canónico vs muerto) y
completar la limpieza de Fase 1 sin romper nada, verificando consecuencias antes de
cada acción.

## Criterio de clasificación

- **CANÓNICO**: componente con consumidores activos (importadores, systemd, Makefile, tests).
- **MUERTO**: componente sin ningún consumidor — candidato a archivo en `.attic/`.

## Clasificación verificada (2026-08-06)

| Componente | Estado | Evidencia |
|---|---|---|
| `tools/benchmarks/` (15 scripts) | ✅ Archivado a `.attic/tools/benchmarks/` | Movido con NO_TOCAR.md (commit previo) |
| `tools/benchmarks/benchmark_ke.py` | ✅ Archivado (Fase 1 residual) | `git mv` → `.attic/`; import guard + skipif en `tests/pending/test_evaluation_corpus.py` (29 tests skip limpio) |
| `tools/` (directorio) | ✅ Eliminado (vacío, sin archivos trackeados) | `rmdir` tras mover benchmark_ke |
| `.bak` / `.bak_repair` | ✅ 0 restantes en árbol | `find` — limpiados (commit paralelo + verificación) |
| `data/`, `mutants/`, `__pycache__/` | ✅ En `.gitignore` | Líneas 77-82 (añadidas por commit `b5088736`) |
| `core/agents/cli.py` | ✅ **RESTAURADO** (era vivo, no muerto) | 3 consumidores: `__init__.py:1`, `tests/unit/test_agents_cli.py` (8 tests), systemd `ura-healing`/`ura-ejecutor` (`-m core.agents.cli`). Renombrado por error en `b5088736` → restaurado en `8cad8280` |
| `scripts/pro/chaos_test.py` | ✅ Canónico (no huérfano) | Conectado a Makefile (`make chaos`) + `manage_timers` (`ura-chaos` timer mensual) |
| `core/mochila/providers/` | ✅ **VIVO — NO TOCAR** | 5 importadores activos; Fase 2 v4.0 (Ramón + otro agente) |
| `core/memoria/` | ✅ **VIVO — NO TOCAR** | 19 importadores activos; Fase 2 v4.0 (Ramón + otro agente) |

## Acciones ejecutadas (Fase 1 residual)

| # | Acción | Resultado | Commit |
|---|---|---|---|
| 1 | Limpiar `__pycache__` del código vivo | 108 directorios eliminados | `1958925d` |
| 2 | Archivar `benchmark_ke.py` → `.attic/` | Movido; `tests/pending/test_evaluation_corpus.py` con import guard + skipif (29 tests skip, 0 errores de colección) | `1958925d` |
| 3 | Eliminar `tools/` vacío | Directorio sin archivos trackeados | `1958925d` |
| 4 | Restaurar `core/agents/cli.py` (rompido por commit paralelo `b5088736`) | 7 errores de colección → 0; validate OK | `8cad8280` |
| 5 | Fix raíz del conflicto recurrente de timer (ver abajo) | `generate` ya no puede regenerar sintaxis inválida | `a3570018` |

## Conflicto latente resuelto de raíz: timer `ura-cleanup-auto`

**Problema:** el agente paralelo revertía el timer a `OnCalendar=*-*-* *:00/6:00:00`
(sintaxis INVALIDA, verificada con `systemd-analyze calendar`: "Argumento inválido")
repetidamente (5-6 veces), restaurando mi fix `*:0/6` una y otra vez.

**Causa raíz:** `scripts/pro/manage_timers.py:45` tenía el mapa de frecuencias con
`"6h": "*-*-* *:00/6:00:00"` — y `tests/integration/test_manage_timers.py:25`
CONVALIDABA esa sintaxis rota. El agente paralelo ejecuta `manage_timers.py generate`,
que regeneraba el timer con la sintaxis inválida, pisando el fix.

**Fix (commit `a3570018`):**
- `manage_timers.py:45`: `"6h": "*:0/6"` (válido)
- `test_manage_timers.py:25`: expectativa actualizada a `*:0/6`
- Verificación: `generate` re-ejecutado → diff vacío, produce `*:0/6`; las otras 7
  frecuencias (daily/weekly/monthly) ya eran válidas (verificadas con systemd-analyze)

**Resultado:** el agente paralelo ya NO puede volver a romper el timer — la fuente
genera la versión correcta. No fue necesaria inmunización (`skip-worktree`).

## No tocado (decisiones explícitas)

- `.gitignore` duplicados (líneas 78-82 vs 3-4/42/75): inofensivos (git usa unión de
  patrones); archivo compartido con agente paralelo → riesgo sin beneficio.
- `core/agents/__init__.py`, tests de agents, servicios systemd: por indicación de Ramón.
- `core/mochila/providers/`, `core/memoria/`: Fase 2 v4.0 (Ramón + otro agente).

## Pendiente Fase 2 (NO es de este agente)

- Migración/limpieza de `core/mochila/providers/` y `core/memoria/` (vivos).
- Pipeline: consolidación restante.

## Verificación final

- `make validate` ✅ OK (test-fast + lint + mypy + radon + hooks)
- `git status` limpio
- 9/9 tests manage_timers, 18/18 quality_gate, pre-commit pytest OK
