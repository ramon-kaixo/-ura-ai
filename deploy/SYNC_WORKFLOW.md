# Flujo de Trabajo de Sincronización Mac → ASUS

## Problema Resuelto

**Error rsync status 23**: El script `sync_to_asus.sh` fallaba cuando Mac estaba en modo inmutable (chflags uchg) porque rsync con `--delete` no podía determinar qué archivos borrar en ASUS.

## Solución Implementada

### 1. Gestión Inteligente de Inmutabilidad en `sync_to_asus.sh`

El script ahora:
- **Detecta** si Mac está en modo LOCKED
- **Desbloquea temporalmente** usando `git-unlock` antes del rsync
- **Ejecuta rsync** sin interferencias
- **Re-bloquea automáticamente** usando `git-relock` después del sync exitoso
- **Rollback automático** si falla el rsync (re-bloquea para mantener seguridad)

### 2. Wrapper `sync_workflow.sh`

Script de alto nivel con 3 modos de operación:

#### Modo `lock-and-sync` (Producción)
```bash
bash deploy/sync_workflow.sh lock-and-sync
```
- Bloquea Mac primero
- Sincroniza (desbloquea temporalmente internamente)
- Mac queda LOCKED al final
- **Uso**: Para producción donde Mac debe estar siempre bloqueado

#### Modo `unlock-sync-lock` (Desarrollo)
```bash
bash deploy/sync_workflow.sh unlock-sync-lock
```
- Desbloquea manualmente
- Sincroniza
- Re-bloquea al final
- **Uso**: Para desarrollo donde necesitas ediciones entre syncs

#### Modo `sync-only` (Automatizado)
```bash
bash deploy/sync_workflow.sh sync-only
```
- Solo sincroniza
- `sync_to_asus.sh` gestiona inmutabilidad automáticamente
- **Uso**: Para automatización (cron, systemd)

#### Modo `status`
```bash
bash deploy/sync_workflow.sh status
```
- Muestra estado de inmutabilidad
- Verifica conectividad con ASUS

## Flujo de Trabajo Recomendado

### Desarrollo Local
1. Desbloquear Mac: `bash deploy/immutable_mac.sh unlock`
2. Editar código
3. Validar: `python3 tests/test_unit.py`
4. Sincronizar: `bash deploy/sync_workflow.sh unlock-sync-lock`
5. Mac queda bloqueado automáticamente

### Producción
1. Mac siempre LOCKED
2. Sincronizar: `bash deploy/sync_workflow.sh lock-and-sync`
3. Mac permanece LOCKED

### Automatización
```bash
# En crontab o systemd
0 */6 * * * cd /Users/ramonesnaola/URA/ura_ia_1972 && bash deploy/sync_workflow.sh sync-only
```

## Archivos Modificados

1. **`deploy/sync_to_asus.sh`**
   - Agregada gestión inteligente de inmutabilidad
   - Rollback automático en caso de fallo
   - Logging mejorado

2. **`deploy/sync_workflow.sh`** (nuevo)
   - Wrapper de alto nivel
   - 3 modos de operación
   - Status check integrado

## Validación

### Verificar estado actual
```bash
bash deploy/immutable_mac.sh status
bash deploy/sync_workflow.sh status
```

### Probar sync en modo desarrollo
```bash
bash deploy/sync_workflow.sh unlock-sync-lock
```

### Probar sync en modo producción
```bash
bash deploy/immutable_mac.sh lock
bash deploy/sync_workflow.sh lock-and-sync
```

## Notas de Seguridad

- **Rollback automático**: Si rsync falla, Mac se re-bloquea automáticamente
- **Exclusiones**: `.URA_IMMUTABLE_STATE` y `immutable_mac.sh` se excluyen del rsync
- **Pre-flight validation**: 139 tests deben pasar antes de sincronizar
- **Post-flight validation**: Tests se ejecutan en ASUS después del sync

## Solución de Problemas

### rsync sigue fallando
1. Verificar conectividad: `ping 10.164.1.99`
2. Verificar permisos SSH: `ssh ramon@10.164.1.99 ls -la /home/ramon/URA/ura_ia_1972`
3. Verificar logs: `cat logs/sync_to_asus.log`

### Mac no se re-bloquea
1. Verificar estado: `bash deploy/immutable_mac.sh status`
2. Re-bloquear manualmente: `bash deploy/immutable_mac.sh lock`
3. Verificar logs: `cat logs/sync_workflow.log`

### Tests fallan en pre-flight
1. Ejecutar tests manualmente: `python3 tests/test_unit.py`
2. Corregir errores
3. Reintentar sync
