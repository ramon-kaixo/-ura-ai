# AUDITORÍA DE ARQUITECTURA — Tuneladoras

**Fecha:** 2026-07-20  
**Componentes analizados:** 4 (999 líneas total)

---

## 1. Responsabilidades

### `tuneladora_master.py` (237 líneas)
- **Principal:** Orquestar modo delta/profundo, lanzar workers, guardar snapshot
- **Secundaria:** Calcular métricas delta, formatear informes, ejecutar ruff
- **SRP:** ❌ Viola — mezcla orquestación con lógica de negocio (cálculo delta, formateo de informes)
- **Funciones que pertenecen a otro componente:** El formateo del informe (líneas 126-137, 222-234) debería estar en un módulo de reporting separado

### `tuneladora_mantenimiento.py` (525 líneas)
- **Principal:** Pipeline de mantenimiento con 3 niveles (ligero/medio/profundo)
- **Secundaria:** Health checks, detección de dispositivos, forense de aislamientos, commit/rollback git, diagnóstico de conciencia
- **SRP:** ❌ Viola masivamente — 30 funciones que mezclar health checks, refactor, git, conciencia, forense, dispositivos de red
- **Funciones que pertenecen a otro componente:** `check_dispositivos()`, `check_ollama()`, `check_model_router()` (monitoreo), `git_commit_if_stable()`, `git_rollback()` (git), `step_diagnostico_conciencia()` (conciencia), `step_forense_aislamientos()` (SNC)

### `tuneladora_mejora.py` (108 líneas)
- **Principal:** Ejecutar pipeline plugin-based en 3 fases
- **Secundaria:** Ninguna — es puramente orquestación
- **SRP:** ✅ Respeta — solo orquesta, delega ejecución a plugin_registry
- **Nota:** Depende de `plugin_registry.py` que a su vez tiene un `log()` roto

### `launch_refactor_gx10.sh` (129 líneas)
- **Principal:** Lanzar 4 workers de refactorización en paralelo + watchdog
- **Secundaria:** Handshake con sistema nervioso, informe SCA, delta snapshot
- **SRP:** ❌ Viola — mezcla lanzamiento de procesos con análisis de métricas y generación de informes

---

## 2. Flujo de llamadas

```
ESTADO ACTUAL (4 archivos, 0 callers activos):

[timer systemd ROTO]  ←──  tuneladora-mantenimiento.timer (dead symlink)
[timer systemd ROTO]  ←──  tuneladora-mantenimiento-semanal.timer (dead symlink)
[timer systemd ACTIVO] ←──  ura-maintenance.timer → mantenimiento/ura_maintenance.py (OTRO archivo)

Ninguno de los 4 archivos tiene caller activo.

Dentro del grafo huérfano:
  tuneladora_master.py ──→ launch_refactor_gx10.sh (subprocess)
  tuneladora_master.py ──→ openclaw_firmador.delta_snapshot (import directo)
  
  tuneladora_mantenimiento.py ──→ 20+ scripts vía subprocess (sin caller)
  tuneladora_mejora.py ──→ plugin_registry (sin caller)
  launch_refactor_gx10.sh ──→ refactor_large_functions.py (v1, no v2)
  launch_refactor_gx10.sh ──→ refactor_watchdog.py
  launch_refactor_gx10.sh ──→ openclaw_firmador.delta_snapshot (inline Python)
```

**Conclusión:** No existe un grafo real. Son 4 archivos huérfanos que se llaman entre sí pero nadie los llama a ellos.

---

## 3. Duplicación

| # | Duplicación | Archivos | Líneas |
|---|-------------|----------|--------|
| D1 | `log()` — 2 implementaciones rotas | `tuneladora_mantenimiento.py:79` (no-op), `plugin_registry.py:14` (no output) | 2 |
| D2 | Cálculo delta (lectura sistema_map.json + snapshot) | `tuneladora_master.py:56-140` vs `launch_refactor_gx10.sh:16-35,120-128` | ~60 líneas duplicadas |
| D3 | Ruff check/format (3 niveles casi idénticos) | `tuneladora_mantenimiento.py:372-492` (revision_ligera/media/profunda) | ~80% de duplicación entre las 3 |
| D4 | `openclaw_indexer.py scan` | `tuneladora_master.py:64,155`, `launch_refactor_gx10.sh:19` | 3 veces |
| D5 | `delta_snapshot("ultimo_ciclo")` | `tuneladora_master.py:118,200`, `launch_refactor_gx10.sh:126` | 3 veces |
| D6 | `f821_watch.py snapshot/compare` | `tuneladora_master.py:168,191`, `tuneladora_mantenimiento.py:248,253` | 4 veces |
| D7 | `URA_ROOT` definido 5 veces con valores inconsistentes | Los 4 archivos + `openclaw_firmador.py` | 5 |
| D8 | `OLLAMA_URL` vs `ASUS_HOST` para el mismo endpoint | `tuneladora_mantenimiento.py:28` vs `launch_refactor_gx10.sh:57` | 2 env vars distintas |

---

## 4. Acoplamiento

| Tipo | Hallazgo |
|------|----------|
| Dependencias entre pipelines | `tuneladora_master.py` → `launch_refactor_gx10.sh` (única dependencia activa entre los 4) |
| Imports cruzados | `tuneladora_master.py` importa `openclaw_firmador` directamente |
| Variables globales compartidas | Ninguna — los archivos no comparten estado en memoria |
| Config compartida | `URA_ROOT` definido independientemente en cada archivo (sin shared config module) |
| Dependencia circular | **No existe** — los 4 archivos son un DAG lineal roto: master → launch → workers |
| **Acoplamiento real:** | **Casi nulo** — porque nadie los llama. Son 4 islas huérfanas. |

---

## 5. ¿Cuántos pipelines existen realmente?

**CERO.** No hay ningún pipeline activo.

Basado en llamadas reales del código:
- `tuneladora-mantenimiento.timer` → target eliminado (dead symlink, `not-found`)
- `tuneladora-mantenimiento-semanal.timer` → target eliminado (dead symlink, `not-found`)
- `ura-maintenance.timer` → llama a `mantenimiento/ura_maintenance.py`, **no a ninguno de estos 4 archivos**
- Ninguno de los 4 archivos aparece en ningún timer, cron, systemd, u otro orquestador

**Los 4 archivos están huérfanos.** Existen 4 implementaciones de cómo DEBERÍA funcionar un pipeline, pero ninguna se ejecuta.

---

## 6. `tuneladora_master.py` — ¿Orquestador real?

| Componente | Líneas | % | ¿Orquestación? |
|-----------|--------|---|----------------|
| `modo_delta()` | 85 | 36% | Parcial — mezcla decisiones con formateo de informes |
| `modo_profundo()` | 76 | 32% | Parcial — mezcla orquestación con ejecución directa de ruff |
| `_run_ruff()` | 8 | 3% | ❌ Lógica de negocio (no orquestación) |
| `log()` | 10 | 4% | Utilidad |
| Config/imports/doc | 29 | 12% | — |
| main() | 17 | 7% | Orquestación pura |
| Blank lines | ~12 | 5% | — |

**~36% es orquestación real. ~64% es lógica de negocio, utilidad y configuración.** 
No es un orquestador puro — es un orquestador que también hace el trabajo.

---

## 7. `launch_refactor_gx10.sh` — Clasificación

**Es un bootstrap con generación de informes.**

Justificación:
- Su función principal es lanzar procesos en background (líneas 52-68)
- Pero también hace handshake con sistema nervioso (líneas 16-35)
- Y genera informes de auditoría (líneas 86-118)
- Y guarda snapshots delta (líneas 120-128)

**No es un pipeline** (no tiene secuencia de fases).
**No es un motor de ejecución** (no gestiona el ciclo de vida de los workers más allá de lanzarlos).
**Es un script de lanzamiento con efectos secundarios de análisis.**

---

## 8. Riesgos

| # | Riesgo | Severidad | Evidencia |
|---|--------|-----------|-----------|
| R1 | **Código muerto:** 999 líneas sin ejecutar | 🔴 Alta | Ningún timer activo llama a estos archivos |
| R2 | **Documentación falsa:** AGENTS.md dice "systemd timer cada 6h" | 🔴 Alta | El timer no existe — el activo llama a otro archivo |
| R3 | **Dos pipelines decidiendo lo mismo:** mantenimiento y master tienen lógica de niveles duplicada | 🟡 Media | `detectar_nivel()` en mantenimiento, `DIA == 1` en master |
| R4 | **Refactor v1 vs v2:** scripts inconsistentes | 🟡 Media | launch usa v1, mantenimiento usa v2 |
| R5 | **Logging roto:** 2 sistemas que no registran nada | 🟡 Media | `pass` en mantenimiento, formato sin output en plugin_registry |
| R6 | **Config duplicada:** URA_ROOT 5 veces, OLLAMA_URL inconsistente | 🟡 Media | 3 valores distintos para la misma ruta |
| R7 | **Sin tests:** 0 archivos de test para 999 líneas | 🟡 Media | `grep -r` no encuentra referencias |
| R8 | **Responsabilidades mezcladas:** health checks, git, conciencia, forense en el mismo archivo | 🟡 Media | mantenimiento.py tiene 30 funciones de 6 dominios distintos |
| R9 | **Bug: `detectar_nivel()` nunca devuelve "medio"** | 🔵 Baja | línea 97: condición muerta |
| R10 | **Bug: `log()` en plugin_registry no produce output** | 🔵 Baja | línea 14-15: strftime sin print |

---

## 9. Propuesta — Arquitectura objetivo

```
┌──────────────────────────────────────────────────────────────┐
│               ARQUITECTURA OBJETIVO (1 pipeline)              │
├──────────────────────────────────────────────────────────────┤
│                                                               │
│  timer systemd ──→ tuneladora.py  (ORQUESTADOR PURO)          │
│                         │                                      │
│                         ├──→ fase 1: preflight                │
│                         │     (token_screen, scanner, health)  │
│                         │                                      │
│                         ├──→ fase 2: refactor                 │
│                         │     (workers v2, watchdog)           │
│                         │                                      │
│                         ├──→ fase 3: validación               │
│                         │     (ruff, audit, f821)              │
│                         │                                      │
│                         └──→ fase 4: cierre                   │
│                               (delta_snapshot, informe, git)   │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐  │
│  │  shared/ (config, log, devices, git, snapshot)          │  │
│  └─────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

**Principios:**
1. **Un solo orquestador** — `tuneladora.py` puro (sin lógica de negocio)
2. **Plugins para todo** — cada fase descubre scripts vía `plugin_registry`
3. **Config centralizada** — `URA_ROOT`, `OLLAMA_URL`, etc. en un solo módulo
4. **Logging único** — un solo `log()` que funciona
5. **Un solo refactor script** — siempre v2
6. **Snapshots automáticos** — cada fase guarda estado

---

## 10. Clasificación

### D. Rediseño completo.

Justificación con evidencia:

1. **Los 4 archivos están huérfanos.** Ningún timer activo los llama. El timer documentado en AGENTS.md (`tuneladora.timer`) no existe. El timer real (`ura-maintenance.timer`) llama a `mantenimiento/ura_maintenance.py`, un archivo diferente.

2. **Hay 2 paradigmas en conflicto.** `tuneladora_mantenimiento.py` usa 30+ steps hardcodeados. `tuneladora_mejora.py` usa plugin discovery. Ambos resuelven el mismo problema de forma incompatible.

3. **Hay versiones divergentes.** `launch_refactor_gx10.sh` usa `refactor_large_functions.py` (v1). `tuneladora_mantenimiento.py` usa `refactor_large_functions_v2.py` (v2). No hay garantía de qué versión se ejecuta.

4. **El logging no funciona en ninguna de las implementaciones.** 2 sistemas rotos (no-op y sin output). Cualquier diagnóstico en producción es imposible.

5. **No tiene tests.** 999 líneas, 0 tests. No hay manera de verificar que un cambio no rompa nada.

6. **La arquitectura actual no es rescatable mediante reducción o fusión** porque los 4 archivos no realizan la misma función — implementan enfoques diferentes e incompatibles. Fusionarlos requeriría reescribir la lógica de todos modos.

**Puntuación arquitectónica: 2/10.** El concepto es correcto (mejora continua automatizada), pero la implementación está fragmentada, huérfana y sin verificación.
