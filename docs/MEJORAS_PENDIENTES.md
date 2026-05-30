# Mejoras Arquitectónicas Pendientes

**Fecha:** 2026-05-11
**Razón:** Requieren refactor mayor o decisiones del usuario. NO se aplicaron automáticamente para evitar romper funcionalidad.

## #6 Centralizar gestión de servicios

**Actual:** launchd + PM2 + systemd (GX10) + Docker + OpenClaw daemon coexisten.

**Propuesta:**
- Mac → solo `launchd` (LaunchAgents) para servicios persistentes.
- GX10 → solo `systemd`.
- Eliminar PM2 (migrar `ura-panel`, `ura-health-tria` a LaunchAgents).

**Riesgo:** Alto (puede romper arranque automático). Requiere pruebas.

## #13 Consolidar agentes redundantes

**Actual:** 90 archivos en `agents/`, incluyendo:
- 7 agentes de cocina (`agente_cocina_*.py`)
- 7 agentes de vocabulario (`agente_vocabulario_*.py`)
- 3 agentes de marketing

**Propuesta:** Crear `agente_dominio.py` con sub-skills cargables. Reducir a ~30 agentes.

**Riesgo:** Alto (puede romper integraciones existentes). Migración por fases.

## #17 Fusionar dashboards

**Actual:** `ura_panel.py` (34KB) + `ura_dashboard.py` (11KB).

**Propuesta:** Un solo dashboard con módulos: triángulo, RAM/CPU/GPU, tokens/s.

**Riesgo:** Medio. Hacer A/B comparando funcionalidad.

## #18 Logs JSON estructurados

**Actual:** `ura_app.log` (451 KB) en texto plano.

**Propuesta:** Migrar `core/logging_config.py` a `python-json-logger`.

**Riesgo:** Bajo. Cambio retrocompatible si se hace bien.

## #12 Migrar a `uv` o `poetry` con lockfile reproducible

**Estado parcial:** `requirements.lock.txt` generado con `pip freeze`.

**Próximo paso:** `uv init && uv add -r requirements.txt` o `poetry init`.

**Riesgo:** Bajo, pero requiere migrar el entorno virtual.

## ~~Mistral-large~~ ELIMINADO — 2026-05-11

**Diagnóstico confirmado:** Requiere 161 GiB, GX10 tiene 133 GiB disponibles (121 GB física).
Dos descargas y dos tests produjeron el mismo error. Inviable en este hardware.

**Acción tomada:** `ollama rm mistral-large`. 73 GB liberados.
**Modelo activo:** qwen3:32b-q8_0 (34 GB, ~6s respuesta, funcional).
