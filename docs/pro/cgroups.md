# cgroups — Gestión de Ciclo de Vida a Nivel de Kernel

## Propósito
Eliminar la dependencia de `fuser` y `os.kill` (espacio de usuario) para
la gestión de procesos huérfanos. Usar cgroups v2 + systemd para que
el kernel mate automáticamente toda la jerarquía de procesos cuando
el servicio principal muere.

## Por qué
- Procesos en estado D (Uninterruptible Sleep) no responden a SIGKILL
- `fuser -k` puede fallar si el socket está en CLOSE_WAIT
- Los hijos huérfanos (ppid=1) consumen recursos hasta que el admin
  los mate manualmente
- systemd ya soporta KillMode=control-group que mata todo el cgroup

## Configuración

### 1. Slice de URA
Crear `/etc/systemd/system/ura-services.slice`:

```ini
[Unit]
Description=URA Services Slice
Before=slices.target

[Slice]
MemoryAccounting=yes
CPUAccounting=yes
IOAccounting=yes
TasksAccounting=yes
```

### 2. Asignar servicios a la slice
Cada servicio URA debe incluir:

```ini
[Service]
Slice=ura-services.slice
KillMode=control-group
MemoryMax=4G
TasksMax=512
```

### 3. Servicios objetivo
| Servicio | Prioridad | MemoryMax |
|----------|-----------|-----------|
| ura-mochila.service | Alta | 4G |
| ura-executor.service | Alta | 2G |
| model-router.service | Media | 1G |
| ura-detector.service | Baja | 2G |

### 4. Verificación
```bash
systemd-cgtop                    # Ver uso por cgroup
systemctl show ura-mochila.service -p ControlGroup  # Ver cgroup asignado
cat /sys/fs/cgroup/system.slice/ura-services.slice/memory.current
```

## Comportamiento con KillMode=control-group
- `systemctl stop ura-mochila.service` → mata todo el grupo
- Si el proceso padre crashea (SIGKILL) → kernel mata a todos los hijos
- Los forks del servicio (workers, threads) mueren automáticamente
- No necesita escaneo de /proc ni scripts de limpieza de huérfanos

## Riesgos
- No hacer `systemctl kill` sobre un servicio sin antes migrar su estado
- Los procesos hijos que deben sobrevivir al padre deben ir en otro cgroup
- Probar en sandbox antes de aplicar a producción

## Referencias
- systemd.resource-control(5)
- cgroups(7)
- https://www.kernel.org/doc/html/latest/admin-guide/cgroup-v2.html
