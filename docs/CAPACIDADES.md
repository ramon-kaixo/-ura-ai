# Capacidades de URA — 2026-08-05

## ✅ Funcional (automatizado)

| Capacidad | Cómo | Estado |
|---|---|---|
| Validar código (16 fases) | tuneladora | ✅ |
| Notificar fallos del pipeline | notifier.py (log/memoria/terminal/systemd) | ✅ |
| Detectar regresiones de cobertura | coverage en reporte + auditoria_continua | ✅ |
| Quality gate (coverage/tests thresholds) | quality_gate.py conectado al pipeline | ✅ |
| Auditoría de salud (10 checks) | auditoria_paralela.py + make audit | ✅ |
| Orquestar tareas (8 fases) | orquestador.py + task.json | ✅ |
| Memorias (4 capas) | episódica/LTM/semántica/corto plazo | ✅ |
| Timers de automatización | manage_timers.py + unidades en deploy/timers | ✅ |
| Hooks de git | post-commit opcional + change_log | ✅ |
| Alertas de supervisor | auditoria_continua → memoria episódica | ✅ |

## ⚠️ Parcial

| Capacidad | Estado |
|---|---|
| Cobertura por módulo en reporte | global sí; por módulo depende de coverage.xml |
| Auto-commit | Desactivado (ADR-221) — reactivable con env var |
| Timers systemd instalados | Unidades generadas; instalación requiere sudo (rootfs RO) |

## ❌ No (por diseño)

| Capacidad | Razón |
|---|---|
| Auto-commit | ADR-221 (aprobación humana) |
| Aura Chat | Fase post-núcleo |
| Módulos de negocio | Siguiente fase |
