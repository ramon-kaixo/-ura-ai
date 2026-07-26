# AUDITORIA COMPLETA URA — 2026-07-27
> Generada por script automatizado en 14 fases. **No se dejo nada fuera.**
> Repo: `~/URA/ura_ia_1972` | Host: `gx10-64c3` | Usuario: `ramon`

---

## RESUMEN EJECUTIVO

| Categoria | 🔴 Criticos | 🟡 Altos | 🟢 Medios | ✅ OK |
|-----------|------------|----------|-----------|-------|
| Servicios | 7 fallidos + 1 duplicado | 8 timers sin documentar | 10 inactivos | 24 activos |
| Seguridad | 1 sudoers NOPASSWD:ALL (FIXED) | secrets.env world-readable (FIXED) | 0 SUID/SGID | SSH keys OK |
| Codigo | 20 funciones >100 lineas | 17 sys.exit en libs | 9 imports circulares | 2,795 tests |
| Config | 23 URA_ROOT duplicados | 6 RUTAS_CONFIG duplicadas | 2 load_dotenv | 100+ JSON dispersos |
| Infra | 32 puertos abiertos | 12 docker-compose | 5 stashes activos | 643 .diff files |
| Tests | — | — | 1 skip | 2,795 collected, 131 files |

---

## FASE 1: INVENTARIO DEL REPO

- **Total archivos:** 21,348
- **Archivos Python:** 3,702
- **Archivos JSON:** 10,427
- **Archivos .diff:** 643
- **Tamano repo:** 939 MB
- **Disco sistema:** 1.8 TB, 55% usado

## FASE 2: SERVICIOS SYSTEMD

### ✅ Activos (24)
docker, model-router, ollama, opencode, qdrant, redis, smbd, ura-api, ura-assistant, ura-audit-api, ura-go2rtc, ura-heartbeat, ura-metrics, ura-mkdocs, ura-mochila, ura-openclaw, ura-ssh-guard, ura-ufw-rules, ura-watch-daemon, ura-watchdog-buffer, ura-watcher, ura-watcher-auditoria, ura-xvfb

### 🔴 Fallidos (7)
ura-contraste, ura-detector, ura-hetzner-tunnel, ura-maintenance, ura-router-health (not-found), ura-voice, ura-maintenance-v2

### 🟡 Duplicado
model-router.service (user + system)

### ⏰ Timers (8)
ura-mochila-guard, ura-watchdog, ura-memory-watchdog, ura-auditd-watchdog, ura-pipeline (cada 5min), ura-cleanup, ura-maintenance-v2 (diario), ura-auto-reindex (inactivo)

## FASE 3: RED Y PUERTOS

32 puertos abiertos. 6 desconocidos: 5053, 5678, 8003, 9090, 9091, 11000.
Model Router (11435) sin auth documentada (FIXED: URA_AUTH_ENABLED=true).
Qdrant (6333/6334) expuesto a 0.0.0.0.

## FASE 4: DEPENDENCIAS

- requirements.txt VACIO
- 127 paquetes en venv
- Ruff excluye 15+ directorios del linting

## FASE 5: SEGURIDAD (POST-FIX)

- ✅ `ramon ALL=(ALL) NOPASSWD: ALL` — ELIMINADO
- ✅ `/etc/ura/secrets.env` — 600 (antes world-readable)
- ✅ 0 passwords hardcodeados
- ✅ 0 SUID/SGID
- ⚠️ `ramon-reboot` y `ura-openclaw` sudoers tenian permisos incorrectos (FIXED)

## FASE 6: CONFIG DUPLICADA

- 23 definiciones URA_ROOT dispersas
- 6 duplicados RUTAS_CONFIG_OPENCODE
- 2 load_dotenv en mochila

## FASE 7: TESTS

131 archivos, 2,795 tests, 1 skip (pytest.mark.slow no registrado)

## FASE 8: GIT

1 archivo modificado (httpx_crawler.py), 0 untracked, 5 stashes activos, 9 branches, 10 tags

## FASE 9: LOGS

ura-watch-daemon: 5 errores de permisos en WorkingDirectory (ya resueltos)
ura-mochila: 0 errores

## FASE 10: CODIGO

- 20 funciones >100 lineas (max 304)
- 9 imports circulares core↔motor
- 17 sys.exit() en librerias core/

## FASE 11: DOCKER

6 contenedores activos, 6 imagenes, 12 docker-compose files

## FASE 12: CRON

User: gpu_health cada 30min
Root: monitoreo_urgente cada minuto

## FASE 13: DISCO Y PERMISOS

1.8TB, 55% usado, repo 939MB

## FASE 14: EXTRAS

0 staged, large files en .sandbox_packages y .opencode/

---

## RECOMENDACIONES

### 🔴 URGENTE (hecho hoy)
1. ✅ Eliminar `ramon ALL=(ALL) NOPASSWD: ALL`
2. ✅ `secrets.env` a 600
3. ✅ Auth model-router
4. ✅ Fix GRUB rw permanente

### 🟡 ALTO
5. Centralizar URA_ROOT
6. Eliminar duplicados RUTAS_CONFIG_OPENCODE
7. Eliminar sys.exit() de librerias (17)
8. Resolver imports circulares (9)
9. Registrar pytest.mark.slow
10. Limpiar 643 archivos .diff

### 🟢 MEDIO
11. Mover .sandbox_packages a requirements
12. Documentar timers en manifesto
13. Eliminar servicios fallidos residuales
14. Revisar 5 stashes activos
15. Reducir funciones >100 lineas

---

*Auditoria generada el 2026-07-27*
*Metodo: 14 fases automatizadas, 0 exclusiones*
*Recovery aplicado: GRUB rw, sudoers restrictivo, secrets 600, auth model-router, PartOf eliminado*
