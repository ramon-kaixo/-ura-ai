# PENDIENTES SUDO — comandos para el humano (Ramón)

Preparado por [WEB] (ASUS) el 2026-08-18. Ejecutar en orden, en ASUS (GX10).

## 1. Activar el despertador del auto-dispatcher (TASK-20260816-009, APROBADA)

Causa: rootfs RO impide escribir en /etc/systemd/system sin sudo.

```bash
sudo cp /home/ramon/URA/ura_ia_1972/deploy/ura-despertador.service /etc/systemd/system/
sudo cp /home/ramon/URA/ura_ia_1972/deploy/ura-despertador.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now ura-despertador.timer
```

Verificación esperada (pasarla al WEB):

```bash
systemctl is-active ura-despertador.timer   # -> active
systemctl list-timers ura-despertador.timer # -> próxima ejecución en ~5 min
```

Nota: el despertador solo invoca `scripts/pro/despertador.sh` (lee coordination.json,
dispatcher.py con flock + verificación de conflictos). No ejecuta código por sí mismo.
Sin tareas pendientes, no asigna nada (colas actualmente vacías).

## 2. (Opcional) Cron del usuario — NO NECESARIO

El cron del usuario falló por RO en /var/spool/cron, pero el timer de arriba cubre
la misma necesidad. No se necesita crontab si el timer queda activo.

## 3. (Opcional, con cuidado) Rootfs RO

Hoy se detectó `/var/spool/cron` y `/run/sudo` RO. Si se quiere un crontab de
usuario funcional (no imprescindible), remount rw temporal:

```bash
mount -o remount,rw / && touch /var/spool/cron/.test_rw && rm /var/spool/cron/.test_rw && echo RW_OK
```

⚠️ Solo si se entiende el impacto (fstab ya configura rw en arranque según
AGENTS.md; el estado RO puede ser de sesión). NO ejecutar el punto 3 si el punto 1
ya funciona.

## Estado tras ejecutar

Marcar aquí y avisar al WEB para verificar y cerrar la cadena de trazabilidad:

- [ ] ura-despertador.timer active
- [ ] despertador registra `ultima_ejecucion_despertador` reciente en docs/udo/coordination.json

## 4. REPARAR BACKUP A LA MAC (CRÍTICO — roto desde 2026-05-29)

Causa raíz (diagnóstico WEB 2026-08-18): la clave `~/.ssh/id_backup_mac` quedó con
permisos 755 (world-readable) → ssh la rechaza ("bad permissions") → el backup a la
Mac falla desde el 29 de mayo. Además: el cron `0 3 * * * backup_to_mac.sh` NO está
instalado (rootfs RO) y la IP Tailscale del script (100.123.81.101) no responde ping.

```bash
sudo chmod 600 /home/ramon/.ssh/id_backup_mac
```

Verificación (tras el chmod, pasarla al WEB):

```bash
ssh -i ~/.ssh/id_backup_mac -o IdentitiesOnly=yes ramonesnaola@10.164.1.26 "echo CLAVE_OK"
# y el backup completo:
bash /opt/ura/scripts/backup_to_mac.sh
```

Nota: si la IP Tailscale de la Mac cambió (100.123.81.101 no responde), el script en
/opt/ura/scripts/backup_to_mac.sh habrá que actualizarla (también con sudo por rootfs RO).
El backup local (ura-backup.timer → backup_assistant.py) SÍ está activo; lo que está
roto es la copia a la Mac (redundancia).

## 5. ACTUALIZAR COPIA DEL BACKUP EN /opt + PROGRAMAR (tras fix IP LAN)

El script instalado en /opt es una copia VIEJA (IP Tailscale 100.123.81.101 obsoleta).
La versión del repo usa LAN (10.164.1.26) y está VERIFICADA (backup completando OK).
Además se preparó un timer systemd para programar el backup diario a las 03:00.

```bash
sudo cp /home/ramon/URA/ura_ia_1972/deploy/backup_to_mac.sh /opt/ura/scripts/backup_to_mac.sh
sudo cp /home/ramon/URA/ura_ia_1972/deploy/ura-backup-mac.service /etc/systemd/system/
sudo cp /home/ramon/URA/ura_ia_1972/deploy/ura-backup-mac.timer /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now ura-backup-mac.timer
```

Verificación:
```bash
systemctl is-active ura-backup-mac.timer  # -> active
tail -3 /home/ramon/URA/logs/backup_to_mac.log  # -> "Backup completado"
```

## 6. REINICIAR HEARTBEAT (auto_dumps RO recurrente)

El daemon `ura-heartbeat.service` (PID antiguo) corre en un mount namespace que ve
`/home/ramon/URA/ura_ia_1972/data/auto_dumps` como RO → los auto_dumps fallan cada ~30s
([Errno 30] Read-only). El repositorio es RW en el namespace actual (verificado).
Reiniciar el servicio lo relanza en el namespace correcto:

```bash
sudo systemctl restart ura-heartbeat.service
```

Verificación: `journalctl -u ura-heartbeat --since "2 min ago" | grep -c "auto-dump"` → 0 errores.

## 7. REMOUNT RW DEL ROOTFS (causa raiz de heartbeat RO y tuneladora FAIL)

Diagnóstico WEB 2026-08-18: el host GX10 tiene el rootfs montado RO. Los servicios
systemd (ura-heartbeat, tuneladora) corren en el namespace del HOST → ven
/home/ramon/URA/data como RO → auto_dumps fallan (heartbeat) y la tuneladora no
puede escribir sus mejoras → Pipeline FAILED en bucle (rollback la protege).
El entorno opencode tiene binds rw propios (por eso YO sí escribo), pero el host no.

```bash
sudo mount -o remount,rw /
```

Verificación tras el remount:
```bash
sudo -i bash -c "touch /home/ramon/URA/ura_ia_1972/data/auto_dumps/.rw_test && rm /home/ramon/URA/ura_ia_1972/data/auto_dumps/.rw_test && echo HOST_RW_OK"
journalctl -u ura-heartbeat --since "2 min ago" | grep -c "Read-only"   # -> 0 tras unos min
# y la tuneladora deberia dejar de fallar:
journalctl --since "5 min ago" | grep -c "Pipeline FAILED"              # -> 0
```
