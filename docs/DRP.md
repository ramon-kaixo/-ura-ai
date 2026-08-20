# DRP — Disaster Recovery Plan (URA)

Plan de recuperación ante desastres. Complementa `REFERENCIA_GX10.md` y la
sección de backups de `AGENTS.md`.

## 1. Resumen de activos críticos

| Activo | Ubicación | Riesgo principal |
|--------|-----------|------------------|
| Repo git | `/home/ramon/URA/ura_ia_1972` (ASUS) + remoto GitHub | Pérdida de disco, corrupción |
| Config servicios | `/etc/ura/` (secrets.env, fix-path.conf) | Pérdida de configuración |
| BD del Knowledge Engine | SQLite (`knowledge/`), Qdrant (`~/.qdrant` o `/opt/ura`) | Corrupción parcial |
| Backups | `/opt/ura/backups/` (NVMe GX10) | Mismo disco que el original |
| Config go2rtc | `/opt/ura/config/go2rtc.yaml` (30 streams cámaras) | Pérdida de configuración |
| Systemd units | `deploy/*.service`, timers | Pérdida de definiciones |

## 2. Estrategia de backup

### Backup automático diario
- Script: `/opt/ura/scripts/backup_to_mac.sh` + cron diario 03:00.
- Destino: Mac (`/Users/ramonesnaola/...`). Requiere clave SSH configurada
  manualmente en GX10 (AGENTS.md §Problemas Conocidos).
- Incluye: repo git, `/etc/ura/` configs, BD SQLite.

### Backup unificado
- Script: `scripts/pro/backup_unified.sh` — snapshot unificado de configs y datos.

### Sync de repo
- `scripts/pro/gx10_sync.sh` / `gx10_sync_final.sh` — sincronización Mac ↔ ASUS.
- `scripts/pro/sync_knowledge.sh` — sync de la base de conocimiento.
- Push a GitHub como copia externa del código.

## 3. Puntos de restauración (git)

- Tags de versión: `vX.Y.Z-faseN` (uno por fase cerrada).
- Tags de hito: `hito-pre-consolidacion-20260819` (punto de rollback del plan
  de consolidación 2026-08).
- Rollback rápido: `scripts/pro/safe_rollback.sh` y `shadow_git_rollback.sh`.

## 4. Procedimientos

### Restauración del repo
1. `git clone <remoto> /home/ramon/URA/ura_ia_1972` (o copiar desde backup).
2. `git checkout <tag/hito>` para un punto conocido.
3. Instalar deps: `pip install -r requirements.txt`.

### Restauración de configs
1. Copiar `/etc/ura/` desde el backup (requiere sudo, rootfs RO en host).
2. `systemctl daemon-reload && systemctl restart <servicios>`.

### Restauración de BD
1. Restaurar el SQLite/Qdrant desde el backup de la Mac.
2. Verificar integridad: el EpisodeStore se auto-recrea si está corrupta
   (verificado 2026-08-12).

## 5. Limitaciones conocidas

- **Backups en mismo disco**: `/opt/ura/backups/` está en NVMe del GX10, no es
  redundancia real (AGENTS.md §Problemas Conocidos).
- **Backup a Mac**: requiere clave SSH manual; si no está configurada, el cron
  falla silenciosamente — verificar periódicamente con
  `ls -la /opt/ura/backups/` y el log del cron.
- **Rootfs RO**: la restauración de configs en ASUS requiere remount temporal
  y sudo del humano.

## 6. Verificación recomendada

- [ ] Semanal: comprobar que `/opt/ura/backups/` tiene contenido reciente.
- [ ] Semanal: comprobar que la Mac recibe el backup diario 03:00.
- [ ] Mensual: restaurar el repo en un directorio temporal y correr
      `pytest -q` + `ruff check .` para validar el snapshot.