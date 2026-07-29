# P2: /storage mount — ura-procesamiento-lento

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~10 min

## Diagnóstico
`ura-procesamiento-lento.service` fallaba porque `/storage` no existía.
El script `daemon_procesamiento_lento.sh` hace `mkdir -p /storage/inbox`
que falla si el padre no existe y el usuario no tiene permisos.

## Solución
```bash
mkdir -p /storage
chown ramon:ramon /storage
chmod 755 /storage
```

No se requirió mount adicional — es un directorio en rootfs.
No hay disco extra en GX10 (único NVMe con root+EFI).

## Estado
- `/storage` creado con permisos correctos: ✅
- Subdirectorios `inbox/` y `processed/` creados por el servicio: ✅
- Servicio `ura-procesamiento-lento`: **active (running)** ✅
- PID: 2094011, 2 tasks, 568K RAM

## Logs del servicio
El daemon ejecuta un loop: find en inbox → procesa → sleep 60.
Prioridad nice 19 + ionice -c 3 (mínima prioridad).
