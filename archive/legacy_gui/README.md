# Archivos GUI Legacy Archivados

**Fecha de archivo:** 2026-05-11

## Archivos archivados

1. **main_final.py.archived** - GUI principal (~5000 líneas)
2. **main_entry.py.archived** - Punto de entrada de la GUI

## Razón del archivo

Estos archivos fueron archivados por las siguientes razones:

1. **Segfault:** main_final.py causaba segfaults al ejecutarse
2. **NameErrors:** Contiene 19 NameErrors que nunca fueron corregidos
3. **No uso en producción:** Nunca se ha utilizado en producción real
4. **Reemplazo:** El dashboard web nuevo (dashboard/ura_web.py) lo reemplaza
5. **Tamaño:** ~5000 líneas de código heredado difícil de mantener

## Cambios realizados

Para archivar estos archivos se realizaron los siguientes cambios:

- Movidos a `archive/legacy_gui/` con extensión `.archived`
- Comentados los imports TYPE_CHECKING en 5 archivos:
  - `services/messaging/whatsapp_reader.py`
  - `services/messaging/telegram_reader.py`
  - `services/messaging/email_reader.py`
  - `services/messaging/instagram_reader.py`
  - `handlers/command_handler.py`
- Type hints cambiados de `URAMainWindowFinal` a `Any`

## Cómo restaurar

Si necesitas restaurar estos archivos:

```bash
# Copiar de vuelta a la raíz
cp archive/legacy_gui/main_final.py.archived main_final.py
cp archive/legacy_gui/main_entry.py.archived main_entry.py

# Restaurar imports en los 5 archivos (descomentar las líneas TYPE_CHECKING)
# Cambiar type hints de Any a URAMainWindowFinal

# Hacer commit del cambio
git add main_final.py main_entry.py services/messaging/*.py handlers/command_handler.py
git commit -m "restore: legacy GUI from archive"
```

## Notas

Esta GUI legacy fue reemplazada por:
- Dashboard web: `dashboard/ura_web.py`
- CLI: `ura_cli.py`
- Panel: `ura_panel.py`

No se recomienda su uso sin una auditoría completa y corrección de los errores mencionados.
