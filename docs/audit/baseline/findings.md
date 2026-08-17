# BLOQUE A — Hallazgos completos (P0-P3) con evidencia

**TASK-20260817-014 · 2026-08-17 · Modo auditoría READ-ONLY**

## Leyenda de estados
`✅ RESUELTO` = corregido y verificado · `⏳ PENDIENTE` = requiere TASK/acción · `🔵 FUERA DE ALCANCE` = decisión humana

## P0 — Críticos
**Ninguno detectado.** No hay riesgo activo de seguridad, pérdida de datos o rotura funcional identificado durante A1-A3.

## P1 — Altos

| ID | Componente | Problema | Evidencia | Impacto | Acción propuesta | Responsable | Estado |
|----|-----------|----------|-----------|---------|------------------|-------------|--------|
| P1-01 | `.env` raíz | Permisos 755 con 4 API keys (DEEPSEEK/GEMINI/GROQ/OPENROUTER + URA_API_KEY) | `stat -c '%a %U:%G' .env` → `755 ramon:ramon` (A2) | Credenciales legibles por todo usuario local | `chmod 600 .env` + regla permanente en AGENTS.md | TERM | ✅ RESUELTO (2.5: 600 verificado) |
| P1-02 | `ura-revisiones.service` | FAILED `203/EXEC`: `detectar_revisiones.sh` sin bit de ejecución; detección de REVIEW sin revisor parada | journal 01:40→10:45 todos `203/EXEC` (A2); `ls -la` → `-rw-rw-r--` | Reviews huérfanas no detectadas/notificadas | `chmod +x` script | TERM | ✅ RESUELTO (2.5: 10:50:49 `0/SUCCESS`, "Notificado (Telegram/Pushover)") |
| P1-03 | Instrumentación | `.venv` eliminado en F4: ruff/mypy/bandit NO DISPONIBLES como comandos | `ls .venv/bin/python` → no existe; `command -v ruff` → vacío (A2) | Gates locales degradados (pytest sistema 7 passed OK) | Regenerar `.venv` (`pip install -r requirements.txt`) o fijar deps sistema | TERM + RAMON | ⏳ PENDIENTE → TASK propuesta 015 |
| P1-04 | Artefactos F4 | backups/audit_reports/logs/tuneladora_reports en `/var/tmp/ura_artifacts` (28MB) | `du -sh /var/tmp/ura_artifacts/*` (A2) | Pérdida si /var/tmp se limpia o reinicia | Mover a `/opt/ura/artifacts/` (rootfs rw) | TERM + RAMON | ⏳ PENDIENTE → TASK propuesta 016 |

## P2 — Medios

| ID | Componente | Problema | Evidencia | Acción propuesta | Responsable | Estado |
|----|-----------|----------|-----------|------------------|-------------|--------|
| P2-01 | `.tuneladora/` | 493MB, 24.960 archivos, no versionado, no importado | `git ls-files` = 0; `du -sh` = 493M; imports resuelven a `scripts/pro/tuneladora/` (A2) | Mover a archivo histórico o retirar (autorización) | RAMON | ⏳ PENDIENTE |
| P2-02 | Servicios systemd | ~22 inactivos (maintenance-v2, cleanup, backup, reindex, pipeline, consolidate, chaos, harden, mutmut-daily, network, watchdog, memory-watchdog, mochila-guard, auditd-watchdog, audit-extra, auto-reindex…) | `systemctl list-units --type=service --all` (A2) | Inventario formal: baja o reactivación documentada por servicio | RAMON/WEB | ⏳ PENDIENTE → TASK propuesta 017 |
| P2-03 | `configs/` duplicado | `ia_committee_config.json` aún en índice de main (chattr +i ya retirado); fuente única en `config/` | `git ls-files configs/` → 1 (A2); `lsattr` → sin `i` | Fusionar rama F4 (`ia/TASK-20260816-012`), que ya lo saca del índice | TERM/WEB (revisión F4) | ⏳ PENDIENTE |
| P2-04 | Artefactos raíz | `build/` (679 py), `dist/`, `ura.egg-info/`, `models/`, `mutants/` (811 py) en el árbol | conteos A1 (`find` por dir) | Verificar .gitignore; `git rm --cached` + retirada con autorización | TERM | ⏳ PENDIENTE → TASK propuesta 016 |
| P2-05 | `ura-revisiones` notificador | Tras arrancar correctamente envía notificaciones; si nadie actúa puede generar ruido | log A2.5 "Notificado (Telegram/Pushover)" | Configurar revisor automático o silenciar según prioridad | WEB | 🔵 Decisión |

## P3 — Bajos

| ID | Componente | Problema | Evidencia | Acción | Estado |
|----|-----------|----------|-----------|--------|--------|
| P3-01 | GPU | GB10 al 94% de utilización en ocioso (48°C) | `nvidia-smi` (A2) | Monitorizar 24h; validar carga llama-vision/qwen3-coder | 🔵 Decisión |
| P3-02 | `systemd/` local | `ura-ejecutor|healing|telemetry` en árbol; `ura-ejecutor` disabled | `ls systemd/` + `systemctl list-unit-files` (A1) | Decidir aplicar o documentar como obsoletas | 🔵 Decisión |
| P3-03 | `motor/core/llm/router/strategy.py:100` | `_call_provider` con 12 args posicionales | `ruff --select PLR0917` (B1) | Refactor futuro: dataclass de request (noqa PLR0917 provisional) | 🔵 P3 |
| P3-04 | `motor/observability/tracing_platform.py:362` | `_emit_span` con 12 args | ídem | Refactor futuro: dataclass span (noqa provisional) | 🔵 P3 |
| P3-05 | `motor/core/llm/router/strategy.py:220` | `call_with_fallback` con 8 args | ídem | Refactor futuro (noqa provisional) | 🔵 P3 |
| P3-06 | `motor/intelligence/agents/reflection.py:202` | `_resultado_reflexion` con 8 args | ídem | Refactor futuro (noqa provisional) | 🔵 P3 |
| P3-07 | `motor/core/web/citation/citation.py:168` | `_register_sentence_origin` con 8 args | ídem | Refactor futuro (noqa provisional) | 🔵 P3 |
| P3-08 | `motor/core/fusion/engine.py:85` | `__init__` con 8 args | ídem | Refactor futuro: config dataclass (noqa provisional) | 🔵 P3 |
| P3-09 | `motor/core/llm/monitor.py:42` | `__init__` con 8 args | ídem | Refactor futuro: config dataclass (noqa provisional) | 🔵 P3 |

## Falsos positivos descartados
Véase README.md sección correspondiente (4 ítems con evidencia).

## Tareas UDO derivadas (propuestas, sin registrar)
- **015** (ALTA): regenerar `.venv` y restaurar gates locales (P1-03).
- **016** (MEDIA): relocalizar artefactos a `/opt/ura/` + retirar `.tuneladora/build/dist/egg-info` (P1-04, P2-01, P2-04).
- **017** (MEDIA): inventario formal de servicios systemd (P2-02) y decisión de P2-05/P3.
- Revisión y fusión de F4 (TASK-20260816-012) resuelve P2-03.