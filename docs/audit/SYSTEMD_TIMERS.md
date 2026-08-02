# Timers Systemd + Crontab — URA (2026-08-02)

## Timers systemd activos (sistema)

| Timer | Periodo | Servicio activado | Último | Notas |
|-------|---------|-------------------|--------|-------|
| ura-memory-watchdog.timer | 5 min | ura-memory-watchdog.service | 19:19 | Watchdog memoria |
| ura-mochila-guard.timer | 5 min | ura-mochila-guard.service | 19:19 | Restaura archivos repo (lista fija) |
| ura-watchdog.timer | 5 min | ura-watchdog.service | 19:19 | Watchdog general |
| ura-auditd-watchdog.timer | 5 min | ura-auditd-watchdog.service | 19:20 | Watchdog auditd |
| ura-pipeline.timer | 5 min | ura-pipeline.service | 19:20 | Pipeline rápido |
| ura-maintenance-v2.timer | 6 h (00/06/12/18) | ura-maintenance-v2.service | 18:00 | Tuneladora mantenimiento (ligero) |
| ua-timer.timer | diario | ua-timer.service | 18:41 | Ubuntu Advantage |
| (otros) | — | — | — | apt-daily, logrotate, fstrim, sysstat, tailscale-selfheal, anacron, fwupd, motd-news, update-notifier, systemd-tmpfiles, dpkg-db-backup |

**Total: 8 timers ura activos** (list-timers --all). Los fallidos documentados
en AGENTS.md (ura-aspirador, ura-detector, ura-historiador, etc.) no aparecen
como timers — son servicios que fallan al arrancar.

## Timers systemd de usuario

- Ninguno activo (`systemctl --user list-timers --all` vacío).

## Crontab (usuario ramon)

| Frecuencia | Comando |
|------------|---------|
| */30 min | `gpu_health.py --json` + recovery automático si power-cap detectado (`flock -n /tmp/gpu_health_tuneladora.lock`) |

## Implicaciones para el inventario (Fase 1.1)

- `ura-mochila-guard.timer` ejecuta `git checkout HEAD -- <archivo>` para
  archivos inexistentes de lista fija — NO toca Makefile ni tests (verificado
  por investigación 2026-08-02).
- `ura-maintenance-v2.service` → `tuneladora_mantenimiento.py` (ligero 7s,
  profundo 7d con rollback git). Es el único camino de escritura al repo
  desde timers.
- Watchdogs de 5 min: supervisan servicios, no escriben en repo.
