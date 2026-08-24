# Sesión 2026-08-24/25 — Mantenimiento Tailscale, credenciales y Git

## Qué se hizo
- Migración global de IPs muertas (10.164.1.99, 192.168.1.135, 100.127.206.86) a Tailscale 100.72.103.12 en ~70 archivos entre ambos repos; `/etc/hosts` del Mac corregido por Ramón (gx10/gx10-ts).
- Credenciales saneadas: `scripts/pro/ura-doble` usa `${OPENCODE_WEB_PASS:-}`; `secrets.env` (600) + loaders de shell en ambas máquinas.
- lildax/OpenCode-2.0: URLs migradas; password queda en JSON plano mitigada con permisos 600 (el binario no soporta expansión `${VAR}` — verificado).
- Commits por bloques en ambos repos con hooks íntegros; divergencia resuelta vía rama temporal + cherry-pick en Mac + `reset --soft` en GX10. Remote: `89d9cabf`.
- `scripts/pro/audit_semanal.sh` creado (no programado en cron aún); `build/` regenerado con IPs viejas eliminado.

## Estado final de servicios (verificado)
opencode.service :8081 active (HTTP 401 auth OK) · ollama :11434 active (8 modelos) · tailscaled active · SSH alias gx10 OK.

## Pendientes conscientes
- Password lildax en texto plano dentro de `deploy/lildax_config.json` (histórico del repo) y config vivo Mac — mitigada con 600; rotación recomendada.
- WIP de TERM stageado sin commitear en GX10 (system_config mezcla, router, cmd_ask, committee...) — ver stash TERM-WIP-20260825 y expediente TASK-20260824-001.
- `committee_config.json` protegido con +i tras esta sesión; inventario completo de inmutables pendiente de documentar en REFERENCIA_GX10.md.
