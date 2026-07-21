# Plan de Recuperación — Rootfs Montado en Solo Lectura

## Síntoma
El sistema de archivos raíz se montó como solo lectura (`ro`) al arrancar, impidiendo:
- Operaciones `git push` y `git tag` (fallan por bloqueo de archivos)
- Creación de archivos temporales
- Escritura en `/etc/`, `/var/`, `/tmp/`
- Cualquier operación de escritura en disco

## Causa Probable
Bug conocido del kernel `6.17.0-1021-nvidia` o fallo PCIe transitorio en NVIDIA Blackwell que fuerza al sistema de archivos a montarse en modo readonly como protección contra corrupción.

## Plan de Ejecución

### Paso 1: Remontar en caliente via SSH
```bash
sudo mount -o remount,rw /
```

### Paso 2: Verificar estado
```bash
# Buscar errores de I/O en el kernel
dmesg | tail -n 20 | grep -iE "nvme|ext4|error|ro"

# Verificar que escritura funciona
touch /root/rw_test && rm /root/rw_test
```

### Paso 3: Proceder con git push/tag
Si paso 2 es exitoso, el repo local ya puede escribir.

### Paso 4: Mantenimiento diferido
Programar reinicio con `fsck` para una ventana de mantenimiento:
```bash
# En el próximo reinicio, arrancar en modo recovery
# y ejecutar:
fsck -f /dev/nvme0n1p2
```

Si el remount en caliente falla o el kernel reporta errores de I/O, el disco puede tener daño físico y requiere intervención con USB de recuperación.

## Verificación del Sistema Actual
```bash
mount | grep " / "
cat /proc/mounts | grep " / "
```
