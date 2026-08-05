# Timers systemd de URA

**Fecha:** 2026-08-05
**Gestor:** `scripts/pro/manage_timers.py` (generate/install/status/start/stop)

## Timers definidos (unidades en deploy/timers/)

| Timer | Script | Frecuencia | Descripción |
|---|---|---|---|
| ura-fix | sanear_codigo.py | daily 04:00 | auto-fix de ruff |
| ura-backup | backup_assistant.py | daily 04:00 | backup del repo |
| ura-reindex | reindex_vectors.py | weekly 05:00 | reindexado vectorial |
| ura-audit-extra | auditoria_paralela.py | weekly 05:00 | auditoría paralela (10 checks) |
| ura-harden | hardening_audit.py | weekly 05:00 | auditoría de hardening |
| ura-consolidate | consolidacion.py | weekly 05:00 | consolidación de código |
| ura-cleanup-auto | cleanup_assistant.py | cada 6h | limpieza asistente |
| ura-chaos | chaos_test.py | monthly | chaos engineering |
| ura-dashboard | dashboard.py | permanent | dashboard web (service, sin timer) |

## Instalación

Requiere sudo (rootfs RO en GX10 — no ejecutable sin password):

```bash
python3 scripts/pro/manage_timers.py generate   # unidades en deploy/timers/
sudo cp deploy/timers/*.timer deploy/timers/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ura-fix.timer ura-backup.timer ...
```

## Estado

```bash
python3 scripts/pro/manage_timers.py status
```

## Notas

- Los scripts ya conectados a systemd/cron/hooks existentes NO tienen timer nuevo
  (metrics_server, tuneladora_mantenimiento, gpu_health, watchers — ya automáticos)
- Los timers complementan los targets del Makefile (make fix, make backup, etc.)
