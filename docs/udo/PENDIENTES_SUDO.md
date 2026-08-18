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
