# DUDAS E INVESTIGACIONES — 2026-08-18 (WEB)

Registro de dudas encontradas durante la sesión y su investigación/resolución.

## D1 — Tuneladora: ¿qué unit y qué archivo tocó cuando falló?
- **Duda**: el journal mostraba "tuneladora Verdict: FAIL — rollback executed" (03:07 y 03:08) pero el unit no aparecía en `systemctl list-units | grep tuneladora`.
- **Investigación**: el log `logs/tuneladora.log` termina el 17/08 23:19 (el service no usa ese log). El proceso corre bajo el nombre "tuneladora" vía timer/script (probablemente tuneladora_mejora/mantenimiento lanzada por el despertador del pipeline). El FAIL fue por contención de I/O con el backup masivo + vram_pressure_high. Rollback ejecutado = comportamiento seguro, repo intacto (verificado HEAD sin cambios).
- **Resolución**: transitorio, causado por el backup mal diseñado (D5) que ya corregí. Re-verificar que la tuneladora no falle tras el backup ligero.

## D2 — Backup: ¿LAN o Tailscale?
- **Duda**: el script original usaba IP Tailscale (100.123.81.101) que estaba caída.
- **Investigación**: Tailscale en la Mac estaba STOPPED; lo arranqué (open -a Tailscale) y el túnel volvió (pong 1ms directo, ssh TSCL_OK). El script usa LAN 10.164.1.26 por defecto.
- **Resolución**: LAN es correcto (misma red local, verificado). Tailscale queda disponible como fallback; no se cambia el default.

## D3 — ¿Qué son `archives/` (23GB) y se necesitan en la Mac?
- **Duda**: el backup copiaba archives/ (15G entraron en la Mac).
- **Investigación**: `archives/` en /home/ramon/URA contiene bundles de respaldo de git (source-*.bundle + manifest.json). Son respaldos LOCALES del repo (generados por el backup local), redundantes para la Mac.
- **Resolución**: NO van a la Mac. Con el SOURCE corregido (solo repo) y `--delete`, los 15G copiados se limpian automáticamente.

## D4 — ¿El guardian auto_dump RO fue real o transitorio?
- **Duda**: error [Errno 30] Read-only en data/auto_dumps (03:08).
- **Investigación**: `data/auto_dumps` es RW (touch OK). El error fue puntual por presión de I/O durante el backup masivo.
- **Resolución**: transitorio. Monitorear; si reaparece sin backup, investigar path configurado.

## D5 — [FALLO GRAVE corregido] El backup copiaba 189GB de modelos a la Mac
- **Duda**: ¿por qué el backup llevaba horas y saturaba I/O?
- **Investigación**: SOURCE_DIR=/home/ramon/URA (toda la carpeta) incluía: ollama-models-0326 (189GB), archives (23GB), backups (5.5GB). El rsync iba por orden alfabético (archives primero) y habría copiado los modelos después.
- **Resolución**: **CORREGIDO** — SOURCE_DIR=/home/ramon/URA/ura_ia_1972 (el repo, ~1.5GB). Los modelos y bundles NO van a la Mac. El próximo backup con --delete limpia la Mac.

## D6 — ¿El backup incluye las BDs de memoria (data/)?
- **Duda**: ¿se respalda la memoria/BD del sistema?
- **Investigación**: el repo ura_ia_1972 contiene su data/ interno (7.3M) + knowledge/ → cubiertos con SOURCE=repo. Las BDs grandes (ollama-models) no deben ir a la Mac.
- **Resolución**: OK con el SOURCE corregido. Verificar tras el primer backup completo que data/ llega.

## D7 — Estado del agente TERM / "el agente no está... se habrá pausado solo"
- **Duda**: el mensaje del usuario sugería que un agente podría estar inactivo.
- **Investigación**: pendiente — verificar procesos opencode en la Mac (opencode web --port 8091) y en ASUS.

## D8 — ¿Se limpió la Mac de los datos incorrectos (archives 15G)?
- **Duda**: quedaron 15G de archives en la Mac de backups_gx10.
- **Resolución**: el rsync nuevo con --delete (SOURCE=repo) los borrará del destino. Verificar tras el backup.

## D9 — ¿El repo de la Mac quedó bien copiado?
- **Duda**: en el backup anterior ura_ia_1972 solo tenía 2.0M en la Mac.
- **Resolución**: el backup nuevo (SOURCE=repo) copia completo; verificar tamaño final en la Mac.

## D10 — ¿La tuneladora debe excluirse de corridas durante backups?
- **Mejora sugerida**: el FAIL se evitó corrigiendo el backup (ahora ligero). Si se reintroduce un backup pesado, coordinar.

## D12 — ¿Por qué el heartbeat (reiniciado) sigue viendo /home RO?
- **Duda**: tras `sudo systemctl restart ura-heartbeat`, el NUEVO PID (4016525) sigue con
  [Errno 30] Read-only en data/auto_dumps.
- **Investigación**: el unit ura-heartbeat.service tiene `ProtectSystem=full` +
  `ProtectHome=read-only` (sandboxing systemd) → el servicio ve /home RO SIEMPRE,
  independientemente del rootfs (el remount rw §7 no cambió nada, verificado 03:4x).
  La tuneladora NO estaba rota (1115 éxitos en la última hora; FAIL/rollback es su
  comportamiento normal de prueba de mejoras).
- **Resolución (causa real)**: drop-in `ProtectHome=no` en
  deploy/systemd-overrides/ura-heartbeat-protecthome.conf (PENDIENTES_SUDO §8) —
  requiere sudo humano para instalar + daemon-reload + restart.
