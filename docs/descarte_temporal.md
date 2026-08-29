# Carpeta Temporal de Descarte — `/home/ramon/URA/descarte_temporal/`

## Propósito

Carpeta de **safety-net temporal** para respaldos **no versionados** y **código
obsoleto** que se retiran del repositorio `ura_ia_1972/` pero no se quieren
borrar de forma inmediata. Sirve para conservar material por si acaso, fuera del
flujo de trabajo de git y fuera del árbol del proyecto.

> **No es un backup oficial.** Para backups reales y redundantes existe
> `/opt/ura/backups/` y el backup a Mac. Esta carpeta es solo un salvavidas
> temporal antes del borrado definitivo.

## Regla de borrado

- Los archivos que lleven **más de 90 días SIN USO** se eliminan automáticamente.
- "Sin uso" = sin modificación/lectura/escritura reciente (`-mtime +90`).
- La regla libera espacio de forma segura: si tras 90 días nadie ha tocado el
  archivo, se considera que nadie lo necesita.

## Script y timer asociados

| Componente | Ruta |
|------------|------|
| Carpeta | `/home/ramon/URA/descarte_temporal/` |
| Script de limpieza | `scripts/pro/limpiar_descarte_temporal.sh` |
| Instalador del timer | `scripts/pro/instalar_timer_descarte_temporal.sh` |
| Unit service (systemd) | `deploy/ura-descarte-temporal.service` |
| Unit timer (systemd) | `deploy/ura-descarte-temporal.timer` |

El script se ejecuta **diariamente** vía systemd timer (`ura-descarte-temporal.timer`)
y borra archivos con más de 90 días sin uso:

```bash
find /home/ramon/URA/descarte_temporal -type f -mtime +90 -delete
find /home/ramon/URA/descarte_temporal -type d -empty -delete
```

## Contenido inicial (creado 2026-08-28)

| Contenido | Descripción |
|-----------|-------------|
| `providers_v1_muerto_20260828/` | Proveedores LLM contrato v1 (`core/mochila/providers/*`) retirados del repo |
| `tests_obsoletos_20260828/` | Tests que importaban los providers v1 (código muerto, rompían la colección) |
| `no_versionados_20260828/no_versionados_gx10.tar.gz` | Backup tar de los archivos no versionados de GX10 |
| `secretario_cache_obsoleto_20260828.py` | Script CLI obsoleto (eliminado en Fase B, nadie lo importa) |
| `audit-api-metrics.patch` | Patch de auditoría retirado (superado por versión canónica en `deploy/patches/`) |

## Verificación

```bash
# El timer activo se ve con:
systemctl list-timers --no-pager | grep descarte

# Debe responder la URA-descarte-temporal.timer activo y pendiente (diario)
```

## Instalación

Ejecutar una sola vez en GX10/ASUS (requiere sudo + rootfs RW):

```bash
sudo bash scripts/pro/instalar_timer_descarte_temporal.sh
```

## Fecha de creación

2026-08-28 (TASK-20260828-003).
