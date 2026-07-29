# T6: Servicios Caídos — Reporte

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~15 min

## Problema
Varios servicios URA en estado failed tras boot del 2026-07-27.

## Diagnóstico y Soluciones

### ura-detector.service ✅ FIXED
- **Error**: `ModuleNotFoundError: No module named 'cv2'`
- **Causa**: `cv2` (OpenCV) instalado en `/home/ramon/.local/lib/python3.12/`
  pero `ProtectHome=tmpfs` ocultaba `/home/ramon` con tmpfs vacío
- **Fix**: Cambiar `ProtectHome=tmpfs` → `ProtectHome=read-only`
  en `/etc/systemd/system/ura-detector.service.d/hardening.conf`
- **Estado**: active (running), 58 tasks, 326MB ✅

### ura-hetzner-tunnel.service ❌ EXTERNAL
- **Error**: `root@178.105.81.83: Permission denied (publickey)`
- **Causa**: SSH key no configurada en Hetzner
- **Fix**: Requiere añadir clave pública de GX10 a `~/.ssh/authorized_keys`
  en el servidor Hetzner (178.105.81.83)
- **Estado**: failed — external dependency

### ura-agent-hierarchy.service ✅ STARTED
- **Error**: Estaba inactive, no failed
- **Fix**: `systemctl start` — arrancó correctamente
- **Estado**: active (running) ✅

### ura-procesamiento-lento.service ❌ CONFIG
- **Error**: `/storage` no existe ni está montado
- **Causa**: Script necesita `/storage/inbox` y `/storage/processed`
- **Fix**: Requiere crear/montar volumen `/storage`
- **Estado**: failed — config incompleta

### ura-router-health.service ❌ NOT FOUND
- **Error**: Unit not found
- **Causa**: Nunca se instaló el archivo .service
- **Estado**: no existe

## Servicios Inactivos (Inactivos por diseño)
- `ura-fix-x11-socket`: oneshot (se ejecuta una vez por boot)
- `ura-aspirador`: oneshot (timer-triggered)
- `ura-historiador`: oneshot (timer-triggered)
- Varios `ura-*.service`: disabled/enabled-status

## Resumen
| Servicio | Antes | Después |
|----------|-------|---------|
| ura-detector | failed | active ✅ |
| ura-agent-hierarchy | inactive | active ✅ |
| ura-hetzner-tunnel | failed | failed (external) |
| ura-procesamiento-lento | failed | failed (config) |
| ura-router-health | — | no existe |
