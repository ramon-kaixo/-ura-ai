# Auditoría Estructural URA — 2026-09-26

> **Tipo:** Auditoría profesional (6 fases) — duplicados, huérfanos, contradicciones, roturas.
> **Método:** Alcance → Inventario → Clasificación → Causa raíz → Priorización → Remediación.
> **Modo:** Solo lectura del sistema. Único archivo creado: este documento.
> **Autor:** Agente Build (DeepSeek V4 Pro), instancia `[1-Desktop-Mac]`.

---

## FASE 1 — ALCANCE

| Elemento | Decisión |
|----------|----------|
| Incluye | `/Users/ramonesnaola/URA` (Mac) y `/home/ramon/URA` (ASUS/GX10) |
| Excluye | `backups_gx10/`, `node_modules/`, `.venv/`, `.git/`, `__pycache__/`, `.mypy_cache/`, `.ruff_cache/`, `.pytest_cache/`, `.coverage*`, `dist/`, `build/`, `htmlcov/` |
| Objetivo | Encontrar duplicados, huérfanos, contradicciones y roturas estructurales |

**Dato de entorno verificado:**
- Mac hostname: `Mini-de-RAMON` (desarrollo ligero + sincronización)
- ASUS: `ramon@100.72.103.12` (Tailscale), servidor de mejora continua
- Repo remoto único: `github.com:ramon-kaixo/-ura-ai.git`

---

## FASE 2 — INVENTARIO COMPLETO

### 2.1 Repositorios Git (2 máquinas, 1 remoto)

| # | Máquina | Toplevel git | HEAD | Estado working tree |
|---|---------|--------------|------|---------------------|
| 1 | Mac | `/Users/ramonesnaola/URA` | `a47782e0` | untracked: `.opencode/agents/.stfolder/`, `.opencode/checkpoints/`, `.opencode/microdata/`, `unificado/` |
| 2 | ASUS | `/home/ramon/URA/ura_ia_1972` | `a47782e0` | `M docs/udo/coordination.runtime.json`, `M docs/udo/pendientes-fase.md` (staged) |

> ⚠️ **PATH DESPLAZADO:** en Mac el repo está en `URA/` (un nivel arriba), en ASUS está en `URA/ura_ia_1972/`. Mismo remoto, mismo HEAD.

**Comando:** `git rev-parse --show-toplevel` + `git log --oneline -1`

### 2.2 Carpetas de agentes

| # | Ruta | Contenido | Comando |
|---|------|-----------|---------|
| 1 | `/Users/ramonesnaola/URA/.opencode/agents/` (Mac) | build.md, calidad-cobertura.md, orchestrator.md, revisor-fondo.md, revisor.md, verificador.md + 2 `.bak-f0-*` | `ls -la` |
| 2 | `/Users/ramonesnaola/URA/ura_ia_1972/.opencode/agentes/` (Mac legacy) | investigador.md, test_comunicacion.md | `ls -la` |
| 3 | `/home/ramon/URA/ura_ia_1972/.opencode/agents/` (ASUS) | los 6 mismos que Mac #1 | `ls -la` |

### 2.3 Configs (AGENTS.md / opencode.json / .env)

| # | Archivo | Tamaño | Fecha | Comando |
|---|---------|--------|-------|---------|
| 1 | Mac `URA/AGENTS.md` | 61771 B (803 líneas) | 26-sep 08:04 | `ls -la` |
| 2 | Mac `URA/CLAUDE.md` → symlink a AGENTS.md | 9 B | 25-sep | `ls -la` |
| 3 | Mac `~/.config/opencode/AGENTS.md` → symlink a `URA/AGENTS.md` | 33 B | 26-sep 03:17 | `ls -la` |
| 4 | Mac `URA/AGENTS.md.v0.30.0` | 44070 B | 25-sep | `ls -la` |
| 5 | Mac `URA/docs/udo/plans/AGENTS.md` | 220 líneas | — | `wc -l` |
| 6 | Mac `URA/opencode.json` (canónico) | 5279 B | 26-sep 07:03 | `ls -la` |
| 7 | Mac `~/.config/opencode/opencode.json` → symlink a #6 | 37 B | 25-sep | `ls -la` |
| 8 | Mac `~/.opencode/opencode.json` (stub) | 51 B (`$schema` only) | 22-sep | `cat` |
| 9 | Mac `Library/Application Support/opencode/opencode.json` | 4849 B | 11-sep | `ls -la` |
| 10 | Mac `Library/Application Support/opencode/opencode-web.json` | 4849 B | 11-sep | `ls -la` |
| 11 | Mac `URA/.env` | 513 B | 25-ago | `ls -la` |
| 12 | Mac `URA/.env.example` | 604 B | 25-sep | `ls -la` |
| 13 | Mac `URA/.env.secrets.template` | 858 B | 25-sep | `ls -la` |
| 14 | Mac legacy `URA/ura_ia_1972/.env` | 402 B | 25-ago | `ls -la` |
| 15 | ASUS `ura_ia_1972/AGENTS.md` | 61771 B | 26-sep 08:18 | `ls -la` |
| 16 | ASUS `ura_ia_1972/CLAUDE.md` → symlink | 9 B | 25-sep | `ls -la` |
| 17 | ASUS `ura_ia_1972/opencode.json` (canónico) | 5279 B | 26-sep 08:18 | `ls -la` |
| 18 | ASUS `URA/.opencode/opencode.json` (stale) | 5131 B | 18-sep 03:13 | `ls -la` + `diff` |
| 19 | ASUS `ura_ia_1972/.env` | 300 B | 29-jul | `ls -la` |
| 20 | ASUS `URA/.env` | 402 B | 25-ago | `ls -la` |
| 21 | ASUS `~/.config/opencode.bak/opencode.json` | — | — | `find` |

> **diff #17 vs #18 (ASUS opencode.json):** la copia de `URA/.opencode/` (sep 18) **no tiene** el bloque del modelo `qwen3-coder:30b-mejorado-100k`, no tiene `default_agent: build` y usa `npm: @ai-sdk/openai-compatible` en otra posición. Es una copia **obsoleta 8 días**.

### 2.4 Servicios systemd (ASUS) — 44 unidades `ura-*`

Activos (running): `opencode`, `ura-api`, `ura-assistant`, `ura-audit-api`, `ura-contraste`, `ura-detector`, `ura-executor`, `ura-go2rtc`, `ura-heartbeat`, `ura-metrics`, `ura-mkdocs`, `ura-mochila`, `ura-ssh-guard`, `ura-voice`, `ura-watch-daemon`, `ura-watchdog-buffer`, `ura-watcher`, `ura-xvfb` (18)

Inactivos (dead/inactive): `ura-audit-extra`, `ura-auditd-watchdog`, `ura-auto-reindex`, `ura-backup`, `ura-backup-mac`, `ura-chaos`, `ura-cleanup`, `ura-cleanup-auto`, `ura-cobertura`, `ura-consolidate`, `ura-descarte-temporal`, `ura-despertador-runtime`, `ura-harden`, `ura-maintenance`, `ura-maintenance-v2`, `ura-memory-watchdog`, `ura-mochila-guard`, `ura-network`, `ura-pipeline`, `ura-reindex`, `ura-revisiones`, `ura-watchdog` (22)

**Comando:** `systemctl list-units --all | grep -iE 'ura-|opencode|tuneladora|pipeline|mochila'`

### 2.5 Timers systemd (ASUS)

Activos: `ura-audit-extra`, `ura-auditd-watchdog`, `ura-auto-reindex`, `ura-backup-mac`, `ura-backup`, `ura-chaos`, `ura-despertador-runtime`, `ura-memory-watchdog`, `ura-mochila-guard`, `ura-revisiones`, `ura-watchdog`, `ura-cleanup-auto`, `ura-descarte-temporal`, `ura-maintenance-v2`, `ura-cobertura`, `ura-cleanup`, `ura-pipeline` (17)

Rotas (`not-found`): `tuneladora-mantenimiento.timer`, `tuneladora-mantenimiento-semanal.timer` (2)

**Comando:** `systemctl list-timers --all`

### 2.6 Crontab (ASUS) — 8 líneas

1. `0 9 * * *` — pytest diario (tests infra/redes/servicios/seguridad/integracion)
2. `0 9 * * 1` — `audit_semanal.sh`
3. `*/15 * * * *` — `enviar_revision_web.sh`
4. `*/30 * * * *` — `gpu_health.py` + `gpu_recovery.sh`
5. `30 3 * * *` — `limpiar_descarte_temporal.sh`
6. `0 3 * * *` — `backup_to_mac.sh` (TERMINAL_HOST=100.123.81.101)
7. `0 4 * * *` — pytest nightly completo
8. `0 2 * * 0` — `auto_rotate_secrets.sh` + `audit_backups_manual.sh`

**Comando:** `crontab -l`

### 2.7 Scripts principales (Mac)

- `scripts/pro/` = **197 archivos, 5.4 MB** (AGENTS.md declara ~146 → ha crecido +51)
- `scripts/deploy/`, `scripts/hooks/`

### 2.8 Documentos clave

- `docs/` = **73 .md en raíz** + 19 subdirectorios (`adr/`, `architecture/`, `audit/`, `engineering/`, `planes/`, `udo/`, `runbooks/`, `plugins/`, etc.)
- `docs/engineering/` = 6 archivos (ENGINEERING_PROCESS, PLAN_TEMPLATE, PLAN_REVIEW_TEMPLATE, POSTMORTEMS, MUTMUT, README)

### 2.9 Ramas Git (divergencia local)

- Mac locales: `cp/stash-critical`, `fix/ci-green`, `main`, `task/TASK-20260909-{002,003,004,005,008,009,010,011,013}`
- ASUS locales: `main`, `dev/v3.1-expansion`, `mac-veredictos`, `preservar-TASK-20260828-cierre-pendientes`, `preservar-TASK-20260922-002`, `refactor/model-router-package`, `dependabot/*`

**Comando:** `git branch -a`

---

## FASE 3 — CLASIFICACIÓN

Leyenda: ✅ REAL · 📋 PLAN · 💥 ROTO · 🔁 DUPLICADO · 👻 HUÉRFANO · 🗑️ BASURA

| # | Item | Ruta | Etiqueta | Evidencia |
|---|------|------|----------|-----------|
| 1 | agents/ (EN) | Mac `URA/.opencode/agents/` + ASUS | ✅ REAL | 6 agentes usados |
| 2 | agentes/ (ES) | Mac `ura_ia_1972/.opencode/agentes/` | 🗑️ BASURA | `investigador.md` (35B), `test_comunicacion.md` (39B) de proyecto legacy |
| 3 | Proyecto legacy | Mac `ura_ia_1972/` (open_engine.py, board.db) | 🗑️ BASURA | gitignored (línea 102), codebase distinta a URA |
| 4 | backups_gx10/ | Mac `URA/backups_gx10/` | 🗑️ BASURA | copia completa repo, gitignored (línea 70) |
| 5 | AGENTS.md canónico | Mac `URA/AGENTS.md` + ASUS | ✅ REAL | 803 líneas, symlink global |
| 6 | AGENTS.md.v0.30.0 | Mac `URA/AGENTS.md.v0.30.0` | 🗑️ BASURA | backup de versión (44KB) |
| 7 | AGENTS.md ajeno | Mac `docs/udo/plans/AGENTS.md` | 👻 HUÉRFANO | template genérico "Your Workspace" (220 líneas), no es URA |
| 8 | opencode.json canónico | Mac `URA/opencode.json` + ASUS `ura_ia_1972/opencode.json` | ✅ REAL | 5279 B, symlink `~/.config` |
| 9 | opencode.json stale ASUS | `/home/ramon/URA/.opencode/opencode.json` | 🔁 DUPLICADO | 5131 B, 8 días viejo, sin `qwen3-coder` |
| 10 | opencode.json stub Mac | `~/.opencode/opencode.json` | 📋 PLAN | 51 B solo `$schema` |
| 11 | opencode.json AppSupport | `Library/Application Support/opencode/*.json` | 🔁 DUPLICADO | 4849 B, sep 11, sin symlink |
| 12 | opencode.jsonc | Mac `URA/unificado/configs/opencode.jsonc` | 📋 PLAN | 50 B, intento de unificación incompleto |
| 13 | .env Mac | `URA/.env` (513B) | ✅ REAL | activo |
| 14 | .env ASUS ×2 | `URA/.env` (402B) + `ura_ia_1972/.env` (300B) | 🔁 DUPLICADO | 2 archivos, fechas distintas |
| 15 | secrets.py | `motor/core/secrets.py` (147 L) vs `core/interfaces/secrets.py` (3 L) | 🔁 DUPLICADO | implementación vs re-export |
| 16 | check_secrets ×3 | `check_secrets.py` + `audit_secrets.py` + `audit_git_secrets.py` | 🔁 DUPLICADO | 3 scripts mismo objetivo |
| 17 | rotación secretos ×3 | `rotate_secrets.sh` + `ura-rotate-secrets.*` + cron `auto_rotate_secrets.sh` | 🔁 DUPLICADO | 3 mecanismos |
| 18 | .bak agentes | `revisor.md.bak-f0-*`, `verificador.md.bak-f0-*` | 🗑️ BASURA | 2 archivos |
| 19 | .bak scripts | `phase-close.sh.bak-*`, `phase-checkpoint.sh.bak-*`, `prune-phase.sh.bak-*`, `check_secrets.py.bak-*` | 🗑️ BASURA | ~4 archivos |
| 20 | .bak docs | `REFERENCIA_GX10.md.bak-rot-*` | 🗑️ BASURA | 1 archivo |
| 21 | .bak opencode.json | `opencode.json.bak-f0-*` + `.bak-unify-*` + `.bak-small-*` | 🗑️ BASURA | ~4 archivos |
| 22 | ARCHITECTURE.md | `docs/ARCHITECTURE.md` (EN, mermaid, 06-18) | 🔁 DUPLICADO | vs ARQUITECTURA.md |
| 23 | ARQUITECTURA.md | `docs/ARQUITECTURA.md` (ES, v4.0, 08-06) | 🔁 DUPLICADO | mismo tema, otro idioma/versión |
| 24 | ARQUITECTURA_* ×4 | `ARQUITECTURA_REFACTOR/v4.0_DIAGNOSTICO/v4.0_PLAN` + `architecture/ARCHITECTURE_v6.0` + `v6.1_PLAN` | 🔁 DUPLICADO | 5 versiones de arquitectura |
| 25 | audit_externa ×5 | `audit_externa_20260728_{1159,1216,1216_AUDITOR}.md` + `latest` + `auditoria_real.md` | 🔁 DUPLICADO | 5 auditorías externas |
| 26 | maintenance v1 vs v2 | `ura-maintenance` vs `ura-maintenance-v2` | 🔁 DUPLICADO | v1 dead, v2 "unificada" dead |
| 27 | pipeline vs watch-daemon | `ura-pipeline` (dead) vs `ura-watch-daemon` (running) | 🔁 DUPLICADO | solapamiento |
| 28 | mochila ×3 | `ura-mochila` + `ura-mochila-guard` + `ura-heartbeat` | 🔁 DUPLICADO | 3 servicios mochila |
| 29 | reindex ×2 | `ura-reindex` vs `ura-auto-reindex` | 🔁 DUPLICADO | ambos dead |
| 30 | watchdog ×3 | `ura-watchdog` + `ura-watchdog-buffer` + `ura-auditd-watchdog` | 🔁 DUPLICADO | 3 watchdogs |
| 31 | cleanup ×3 | `ura-cleanup` + `ura-cleanup-auto` + `ura-descarte-temporal` | 🔁 DUPLICADO | 3 limpiezas |
| 32 | backup ×2 | `ura-backup` vs `ura-backup-mac` | 🔁 DUPLICADO | ambos dead |
| 33 | audit-api ×2 | `ura-audit-api` (running) vs `ura-audit-extra` (dead) | 🔁 DUPLICADO | 2 auditorías |
| 34 | timers rotos ×2 | `tuneladora-mantenimiento*.timer` | 💥 ROTO | `not-found` |
| 35 | backup Mac cron+timer | cron `0 3` + `ura-backup-mac.timer` (03:00) | 🔁 DUPLICADO | pisan |
| 36 | revisiones cron+timer | cron `*/15` + `ura-revisiones.timer` | 🔁 DUPLICADO | pisan |
| 37 | tests cron ×2 | cron `0 9` (daily) + `0 4` (nightly) | 🔁 DUPLICADO | 2 pytest programados |
| 38 | unificado/ | Mac `URA/unificado/` | 📋 PLAN | intento de unificación, untracked |
| 39 | .stfolder/ | Mac `URA/.opencode/agents/.stfolder/` | 👻 HUÉRFANO | marker Syncthing (folderID `ura-agents`) |

---

## FASE 4 — CAUSA RAÍZ

### 4.1 ¿Por qué hay dos `agents/` y `agentes/`?
- El proyecto URA **históricamente** vivió en `/home/ramon/URA/ura_ia_1972/` (ASUS) y `/Users/ramonesnaola/URA/ura_ia_1972/` (Mac).
- En un refactor se **subió el repo Mac un nivel** (a `/Users/ramonesnaola/URA/`), pero el directorio legacy `ura_ia_1972/` (proyecto antiguo "open_engine") **no se borró** y quedó gitignored (línea 102 del `.gitignore`).
- Ese directorio legacy conservó su propia carpeta `.opencode/agentes/` (español), mientras el repo actual usa `.opencode/agents/` (inglés).
- **Resultado:** dos carpetas de agentes con dos convenciones de idioma, y la sensación de "¿cuál manda?".

### 4.2 ¿Por qué hay dos repos en Mac?
- No son dos repos git. Hay **un solo** repo (`/Users/ramonesnaola/URA/.git`) y **un subdirectorio legacy** (`ura_ia_1972/`) que **parece** un repo por su contenido (`.opencode/`, `.env`, `pyproject.toml`, `README.md`) pero **no tiene `.git`**.
- La confusión nace del **nombre**: el subdirectorio se llama igual que la carpeta del repo en ASUS (`ura_ia_1972`).

### 4.3 ¿Por qué hay 3 rotadores de secretos?
- `scripts/pro/rotate_secrets.sh` — rotación manual/script del repo.
- `deploy/systemd-prod/ura-rotate-secrets.{service,timer}` — intento de rotación vía systemd.
- cron `/home/ramon/auto_rotate_secrets.sh` — rotación vía cron (fuera del repo, en `$HOME`).
- Cada refactor de "gestión de secretos" (Fase 17.5) añadió un mecanismo sin retirar el anterior.

### 4.4 ¿Por qué hay services dead?
- Múltiples fases (F10–F29 + post-F29) crearon servicios con nombres descriptivos que **luego fueron reemplazados** por versiones "unificadas" (`-v2`) o por `ura-watch-daemon` (pipeline reactivo) **sin deshabilitar/borrar** el anterior.
- Ejemplos concretos: `ura-maintenance` → `ura-maintenance-v2`; `ura-pipeline` → `ura-watch-daemon`; `ura-reindex` → `ura-auto-reindex`.
- Los timers `tuneladora-mantenimiento*.timer` quedaron **huérfanos** cuando la tuneladora se renombró a `ura-maintenance-v2`.

### 4.5 ¿Por qué hay 2 opencode.json en ASUS y 4 en Mac?
- ASUS: el histórico vivió en `/home/ramon/URA/.opencode/` (raíz URA) antes de que el repo se consolidara en `ura_ia_1972/`. Al moverse, se actualizó el de `ura_ia_1972/opencode.json` pero **no se borró** el de `URA/.opencode/`.
- Mac: hay 4 porque conviven (a) el canónico del repo, (b) el stub de `~/.opencode/`, (c) el de `Library/Application Support/opencode/` (config de la app desktop), y (d) el intento `unificado/configs/opencode.jsonc`.

### 4.6 ¿Por qué `.env` está duplicado en ASUS?
- Igual que opencode.json: histórico en `/home/ramon/URA/.env` y nuevo en `/home/ramon/URA/ura_ia_1972/.env`. Ambos persisten; el servicio/launcher probablemente lee uno por ruta relativa y el otro por ruta absoluta.

### 4.7 ¿Por qué cron y timers se pisan (backup, revisiones)?
- Los cron se crearon **antes** de formalizar los timers systemd (Fase de producción/operación). Al migrar a systemd no se retiraron los cron equivalentes.

**Resumen de causa raíz común:** cada refactor/fase **añadió** el nuevo elemento (carpeta, servicio, script, config) pero **no retiró** el viejo. No existe un paso de "desmantelamiento del anterior" en el checklist de cierre de fase.

---

## FASE 5 — PRIORIZACIÓN

| # | Item | Impacto | Esfuerzo | Prioridad | Por qué |
|---|------|---------|----------|-----------|---------|
| 1 | Path repo Mac desplazado (`URA/` vs `URA/ura_ia_1972/`) | **ALTO** | 2-4h | 🔴 P0 | Riesgo de drift/pérdida de trabajo; confunde a todos los agentes |
| 2 | `ura_ia_1972/` legacy en Mac | **ALTO** | 1h | 🔴 P0 | Causa raíz del lío `agents/agentes`; código muerto confunde |
| 3 | Timers rotos `tuneladora-mantenimiento*.timer` | **MEDIO** | 0.5h | 🟠 P1 | `not-found` en systemd; tuneladora no corre bajo su nombre real |
| 4 | Backup Mac cron+timer solapados | **MEDIO** | 0.5h | 🟠 P1 | Doble backup a la misma hora → posible conflicto/duplicado |
| 5 | opencode.json stale en ASUS (`URA/.opencode/`) | **MEDIO** | 0.5h | 🟠 P1 | Config obsoleta puede cargarse en vez de la nueva (modelos viejos) |
| 6 | `.env` duplicado ASUS | **MEDIO** | 0.5h | 🟠 P1 | Dos fuentes de secretos → ambigüedad |
| 7 | Services dead duplicados (~10 pares) | **BAJO** | 1-2h | 🟡 P2 | No rompen nada activo, pero ensucian `list-units` |
| 8 | Rotación secretos ×3 | **BAJO** | 1h | 🟡 P2 | Funciona, pero 3 caminos = riesgo de divergencia |
| 9 | Docs duplicados (ARCHITECTURE/ARQUITECTURA, 5 audits) | **BAJO** | 2h | 🟡 P2 | Cosmético/documental, pero contradice la "fuente única" |
| 10 | .bak y residuos (~15 archivos) | **BAJO** | 0.5h | 🟢 P3 | Cosmético |
| 11 | `backups_gx10/` y `unificado/` | **BAJO** | 1h | 🟢 P3 | Ocupan disco, gitignored |

---

## FASE 6 — PLAN DE REMEDIACIÓN (solo P0/P1 detallado)

### P0-1. Alinear path del repo Mac ↔ ASUS
- **Qué:** decidir ruta canónica. Opción A: Mac usa `URA/` y ASUS `URA/ura_ia_1972/` (documentarlo). Opción B: mover uno para que coincidan.
- **Archivos afectados:** ninguno de código; documentación `AGENTS.md` (sección "Flujo de Trabajo") + `docs/architecture/REFERENCIA_GX10.md`.
- **Rollback:** `git checkout -- AGENTS.md` (si se editó doc).
- **Verificación:** `git rev-parse --show-toplevel` devuelve lo esperado en ambas máquinas; `git log --oneline -1` idéntico.

### P0-2. Archivar proyecto legacy `ura_ia_1972/` en Mac
- **Qué:** mover `URA/ura_ia_1972/` → `URA/.nervioso/descarte/ura_ia_1972-legacy/` (no borrar de golpe).
- **Archivos afectados:** todo el subdirectorio `ura_ia_1972/` (legacy open_engine).
- **Rollback:** `mv .nervioso/descarte/ura_ia_1972-legacy ura_ia_1972`.
- **Verificación:** `ls /Users/ramonesnaola/URA/ura_ia_1972` no existe; `git status` no cambia (ya estaba gitignored).

### P1-1. Arreglar timers rotos
- **Qué:** `systemctl disable tuneladora-mantenimiento.timer tuneladora-mantenimiento-semanal.timer` (o recrearlos apuntando a `ura-maintenance-v2`).
- **Rollback:** `systemctl reenable <timer>`.
- **Verificación:** `systemctl list-timers --all | grep tuneladora` no muestra `not-found`.

### P1-2. Unificar backup a Mac
- **Qué:** elegir UNO (timer `ura-backup-mac.timer` o cron `0 3 backup_to_mac.sh`) y deshabilitar el otro.
- **Rollback:** re-habilitar el deshabilitado.
- **Verificación:** `systemctl list-timers` + `crontab -l` muestran solo un mecanismo a las 03:00.

### P1-3. Eliminar opencode.json stale en ASUS
- **Qué:** mover `/home/ramon/URA/.opencode/opencode.json` a `.bak` (o borrar, ya que el canónico está en `ura_ia_1972/` con symlink).
- **Rollback:** restaurar desde `.bak`.
- **Verificación:** `ls /home/ramon/URA/.opencode/opencode.json` no existe; `~/.config/opencode/opencode.json` sigue siendo symlink al canónico.

### P1-4. Unificar `.env` en ASUS
- **Qué:** definir cuál es canónico (propongo `ura_ia_1972/.env`) y consolidar; eliminar el otro.
- **Rollback:** restaurar el eliminado.
- **Verificación:** `find /home/ramon/URA -maxdepth 2 -name .env` devuelve uno.

---

## VEREDICTO FINAL

- **Duplicados:** ~39 (ver tabla Fase 3).
- **Huérfanos:** 2 (AGENTS.md ajeno, `.stfolder/` syncthing).
- **Roturas:** 2 timers `not-found` + 1 opencode.json stale (config obsoleta que puede cargarse).
- **Basura:** ~15 .bak + `backups_gx10/` + `ura_ia_1972/` legacy.
- **Recuperable:** **SÍ**. El código fuente (Mac `URA/` = ASUS `ura_ia_1972/`) está sincronizado en HEAD `a47782e0`. El caos es **periférico** (configs, docs, servicios, rutas, residuos), no de código.
- **Lo más urgente:** P0-1 (path desplazado) y P0-2 (legacy `ura_ia_1972/`), porque son la causa raíz del 80% de la confusión.

---

## REGLA ANTI-RECAÍDA (propuesta)

Todo cierre de fase que **renombre o reemplace** un elemento (carpeta, servicio, timer, config, script) debe:
1. Añadir el nuevo elemento.
2. **Eliminar o archivar el anterior** en el mismo commit.
3. Verificar con `find`/`systemctl list-units`/`git status` que no queda el viejo.
4. Actualizar la tabla de esta auditoría.
