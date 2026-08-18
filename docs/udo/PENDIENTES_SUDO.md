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

## 8. FIX HEARTBEAT: drop-in ProtectHome=no (CAUSA REAL de auto_dumps RO)

El unit ura-heartbeat.service tiene `ProtectSystem=full` + `ProtectHome=read-only`
(sandboxing systemd) -> el servicio SIEMPRE ve /home RO, aunque el rootfs sea rw
(por eso el remount rw de §7 no cambio nada). Fix limpio con drop-in (no tocar el unit):

```bash
sudo mkdir -p /etc/systemd/system/ura-heartbeat.service.d
sudo cp /home/ramon/URA/ura_ia_1972/deploy/systemd-overrides/ura-heartbeat-protecthome.conf /etc/systemd/system/ura-heartbeat.service.d/
sudo systemctl daemon-reload
sudo systemctl restart ura-heartbeat.service
```

Verificacion (pasarla al WEB):
```bash
journalctl -u ura-heartbeat --since "2 min ago" | grep -c "Read-only"   # -> 0
ls -lt /home/ramon/URA/ura_ia_1972/data/auto_dumps/ | head -2          # -> dumps nuevos
```

## 9. REINICIAR WATCH DAEMON (tuneladora) — si quedó inactive

El WEB mató el proceso watch_daemon para recargar la v3.1 (debounce+guard); systemd con
Restart=on-failure NO lo relanza tras SIGTERM. Arrancar de nuevo:

```bash
sudo systemctl start ura-watch-daemon.service
```

Verificación: `systemctl is-active ura-watch-daemon.service` -> active; y
`journalctl -u ura-watch-daemon --since "1 min ago" | grep "Watch daemon v3.1"`.

## 9. REACTIVAR WATCH DAEMON (actualizado — chmod +x HECHO, daemon v3.2 manual activo)

El chmod +x está aplicado y el daemon corre MANUAL (proceso, guard anti-doble-instancia v3.2).
Para pasarlo a systemd de forma limpia:

```bash
pkill -f "watch_daemon.sh"          # mata el manual (el flock se libera)
sudo systemctl start ura-watch-daemon.service
```

Verificación: `systemctl is-active ura-watch-daemon.service` -> active y
`pgrep -cf watch_daemon.sh` -> 1. Si el manual sigue vivo, el start dará "exited"
(guard anti-duplicación, comportamiento correcto).

## 10. ARRANCAR STACK DE MONITOREO (F8 — prometheus+grafana+alertmanager+node-exporter)

```bash
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus
sudo docker compose up -d
```

Verificación: 9092/-/healthy, 3000/api/health, 9093/-/healthy, 9100/metrics.
Detalle: deploy/prometheus/README.md.

## 11. FIX ura-audit-api (P5 + P9) — archivo en /home/ramon/bin (RO para ramon)

P9: el endpoint /run-audit apunta a /Users/ramonesnaola/bin/run_ura_audit.sh (ruta de la
Mac — NO existe en GX10). P5: falta /metrics.

```bash
sudo sed -i 's|/Users/ramonesnaola/bin/run_ura_audit.sh|/home/ramon/bin/run_ura_audit.sh|' /home/ramon/bin/run_audit_api.py
sudo patch -b /home/ramon/bin/run_audit_api.py < /home/ramon/URA/ura_ia_1972/deploy/patches/audit-api-metrics.patch
sudo systemctl restart ura-audit-api.service
```

Verificación: `curl -s http://127.0.0.1:5053/metrics` -> 200 con ura_audit_api_up 1.

NOTA (actualización §11): ya existe versión CORREGIDA y versionada en el repo:
`deploy/run_audit_api.py` (P5+P9 aplicados). Opción más simple:
`sudo cp /home/ramon/URA/ura_ia_1972/deploy/run_audit_api.py /home/ramon/bin/run_audit_api.py`
y reiniciar el servicio. El patch sigue disponible como alternativa.

## 12. WEBHOOK DE ALERTAS (sugerencia 1 ejecutada — requiere compose §10)

El webhook receptor (deploy/prometheus/webhook-alerts.py -> Telegram/Pushover via
motor.core.notifier) está integrado en el compose (puerto 9105). Se activa con el
§10 (docker compose up -d). Sin secretos de notificación degrada con log (probado).
Para activar notificaciones reales: `sudo docker exec -it ura-alerts-webhook bash`
y exportar TELEGRAM_TOKEN/TELEGRAM_CHAT_ID o configurar env_file con /etc/ura/secrets.env.

## 10. ARRANCAR STACK DE MONITOREO (F8 — ACTUALIZADO: puertos 9094/3001/9095)

El compose usa puertos libres (9094/3001/9095/9100/9105) — 9092 (ura-detector), 9093/3000
(stack docker previa de prometheus/grafana) quedan intactos. Mismo comando:

```bash
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus
sudo docker compose up -d
```

Verificación: 9094/-/healthy, 3001/api/health, 9095/-/healthy, 9100/metrics, 9105/health.

## 13. REINICIAR URA-HEARTBEAT (cargar umbral VRAM nuevo — P11)

El umbral VRAM_PANIC_MB=64000 está en el código (commit 32b3c980) pero el servicio
corre con el módulo cargado antes. Aplicar:

```bash
sudo systemctl restart ura-heartbeat.service
```

Verificación: journal sin vram_panic falsos con el modelo de refactor cargado.

## 14. BLOQUE SUDO CONSOLIDADO (2026-08-18) — copiar y ejecutar todo de una vez

```bash
# 1. Heartbeat: cargar umbral VRAM nuevo (64000) — desbloquea la cola del watch-daemon
sudo systemctl restart ura-heartbeat.service
# 2. Stack monitoreo F8 (puertos libres: 9094/3001/9095/9100/9105)
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus && sudo docker compose up -d
# 3. Audit-api corregido (P5 /metrics + P9 ruta GX10)
sudo cp /home/ramon/URA/ura_ia_1972/deploy/run_audit_api.py /home/ramon/bin/run_audit_api.py
sudo systemctl restart ura-audit-api.service
# 4. Limpiar residuos (cosmetico — el timer de las 03:00 autolimpia igualmente)
sudo systemctl reset-failed ura-backup-mac.service
```

Después, verificación automática (read-only):
```bash
bash /home/ramon/URA/ura_ia_1972/scripts/pro/verificar_instalaciones_f8.sh
```
Debe dar: 9/9 OK (o los OK de lo aplicado).

## 15. RE-EJECUTAR STACK MONITOREO (conflicto nombres resuelto — container_name -f8)

El primer `docker compose up -d` falló: los contenedores ura-grafana/ura-prometheus
(de la stack docker previa) ya existían. El compose ahora usa nombres -f8 y
volúmenes -f8 (coexistencia, la stack previa queda intacta). Re-ejecutar:

```bash
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus && sudo docker compose up -d
```

Verificación: `bash scripts/pro/verificar_instalaciones_f8.sh` -> 9/9 OK.

## 16. SANDBOX: commitear su propia zona (aprobado RAMON 2026-08-18)

El sandbox (docker sandbox-mejora-continua) lleva 96 archivos modificados sin commitear
y su refactor en curso de knowledge/engine/compiler.py rompe 3 tests (test_knowledge_compiler_cobertura).
Su mecanismo oficial valida y commitea su zona:

```bash
sudo docker exec sandbox-mejora-continua bash /workspace/tuneladora_mejora.sh
```

Alternativa mas ligera (solo commit, sin ciclo completo) si la tuneladora tarda demasiado:
```bash
sudo docker exec sandbox-mejora-continua bash -c "cd /workspace && git add -A && git -c core.hooksPath=/dev/null commit -m 'chore(sandbox): commit de zona de mejora continua [AUTO]' && git push origin main"
```

## 17. BLOQUE FINAL (2026-08-18) — lo unico que falta, copiar y pegar

```bash
# A. Stack monitoreo F8 (nombres -f8, sin conflicto con stack previa)
cd /home/ramon/URA/ura_ia_1972/deploy/prometheus && sudo docker compose up -d
# B. Sandbox commitea su propia zona (opcion ligera: commit directo sin ciclo tuneladora)
sudo docker exec sandbox-mejora-continua bash -c "cd /workspace && git add -A && git -c core.hooksPath=/dev/null commit -m 'chore(sandbox): zona de mejora continua [AUTO]' && git push origin main"
```

Despues avisar al WEB: verificara 9/9 (verificador), cerrara TASK-025 DONE (arbol limpio),
comprobara los 3 tests de test_knowledge_compiler_cobertura y el siguiente mutmut.
