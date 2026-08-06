# DEPRECADO — Componentes fuera de servicio v4.0

**Fecha:** 2026-08-06
**Fase:** 8 del Plan v4.0
**Estado:** Lista de componentes MUERTOS o en transición, con destino y evidencia

## 🔴 MUERTOS (0 consumidores — candidatos a archivo/retiro)

| Componente | Evidencia | Destino |
|---|---|---|
| `core/sandbox.py` | 0 importadores; su propio test lo declara muerto | `.attic/core/` |
| `deploy/ia-flujo.service` | Ejecuta `app/` archivado (app/flujo_constante.py nunca existió) | Retirar unit |
| `deploy/ura-mcp.service` | Ejecuta `mcp_mochila.py` archivado; no instalada | Retirar unit |
| `deploy/timers/ura-mutmut.{service,timer}` | Fuera de `manage_timers.py` y de systemd | Integrar o retirar (Ramón) |
| `scripts/pro/pipeline_supremo.py` paso `plan_validator.py` | Script NO EXISTE en repo ni .attic | F6.2: degradar o restaurar |
| `scripts/pro/memoria.py` | NO existe (plan viejo lo citaba) | — |

## 🟡 TRANSICIÓN (vivos por tests pero sin consumidores de producción)

| Componente | Evidencia | Destino |
|---|---|---|
| `core/model_router/` (11 módulos) | 0 consumidores vivos; 6 tests; servicio INACTIVE; `core/model_router_main.py` borrado | Decisión Ramón: archivar o stub |
| `motor/cli/cmd_ura.py` (refs) | Llama `core/model_router_main.py` inexistente (líneas 47,63,106,251) | F6.2: corregir/eliminar refs |
| `scripts/pro/consolidacion.py` | Import roto `scripts.pro.reuse.quality_gates` → `ura-consolidate` FAILED | F6.2 |
| `scripts/pro/dashboard.py` | `goal_manager` archivado → Makefile dashboard roto | F6.2 |

## 🟡 DEGRADADOS (funcionales pero con pasos inertes)

| Componente | Pasos afectados | Evidencia |
|---|---|---|
| `scripts/pro/tuneladora_mantenimiento.py` | token_screen(9), conciencia(9), inspectores(7), compactadora(6), analizar_fallo_conciencia(3), scanner_autoajuste(2), auto_reglas(2), poda_mecanica(1) | Refs a archivados |
| `scripts/pro/pipeline_supremo.py` | token_screen, scanner_autoajuste, inspectores, poda_mecanica, openclaw_reviewer, alineador (archivados), plan_validator (no existe) | 7/10 pasos inertes |

## 🔵 Archivados (registro — por si se necesita recuperar)

Ver `.attic/tools/scripts_pro/` (gitignored). Ejemplos: 27 scripts purga-v4
(revertidos a scripts/pro por decisión de Ramón, commit `f2c4ce93`), 26 cadenas muertas
en `.attic/tools/scripts_pro/purga-v4-cadenas/` (archivo definitivo).

**Nota:** los 27 de purga-v4 fueron devueltos a `scripts/pro/` — NO son deprecados.