# Manifiesto de Determinismo — Sistema URA

> *"El sistema tiene un solo estado correcto: el que está declarado en Git."*

---

## Principio 1 — Fuente de Verdad Única (Single Source of Truth)

Toda la configuración del sistema vive en un solo archivo:
```
config/system_config.json
```

Si un valor no está en ese archivo, **no existe**. Si está en el código pero no en el JSON, **es un bug**.

## Principio 2 — Idempotencia

Ejecutar cualquier script del sistema **10 veces seguidas** debe producir el mismo resultado. No debe haber efectos secundarios acumulativos ni estados inconsistentes.

Para garantizarlo:
- `core/config_manager.py` valida al arrancar que los directorios declarados en config existen
- `ura_maintenance.py` usa lockfile para evitar ejecuciones simultáneas
- El sistema nunca modifica `system_config.json` automáticamente — solo lo lee

## Principio 3 — Prohibición de Cambios Manuales

**Queda prohibido:**
- Editar archivos de configuración directamente en el servidor
- Copiar scripts manualmente entre máquinas (`scp`)
- Crear directorios "a mano" porque el script falló

**En su lugar:**
- Todo cambio se hace en el repositorio Git (`ura_ia_1972`)
- `git commit` + `git push` desde el Mac
- `git pull` en el GX10 (automático vía `ura_maintenance_remote.py`)
- Los scripts detectan el SO y cargan el perfil correcto automáticamente

## Principio 4 — Conciencia de Plataforma (Platform Awareness)

El sistema **nunca asume** en qué máquina está corriendo. Al arrancar:
```python
platform.system()  # 'Darwin' o 'Linux'
```

Y carga el perfil correspondiente de `system_config.json`. Si un path hardcodeado (`/home/ramon`, `/opt/ura`) aparece en el código, **es un bug**.

La API pública de paths es:
```python
from core.config_manager import get_base_dir   # ~/URA o /home/ramon/URA
from core.config_manager import get_ollama_url  # http://host:port
```

## Principio 5 — Validación Idempotente

Al arrancar, `ura_maintenance.py` ejecuta `validate_config()` que verifica:
- Los directorios declarados en `system_config.json` existen
- Tienen permisos de escritura
- Los directorios temporales y de logs son accesibles

Si hay discrepancias, el sistema emite **warnings** y continúa. Si un directorio crítico no existe, **no se crea automáticamente** — el operador debe crearlo o actualizar la config vía Git.

---

## Arquitectura de Vías

```
    Mac (Cliente)                     GX10 (Servidor)
    ┌──────────────┐                  ┌──────────────┐
    │  git commit  │                  │  git pull    │
    │  git push    │ ───────────────→ │  auto-config │
    │              │                  │              │
    │  system_     │   misma fuente   │  system_     │
    │  config.json │ ←── de verdad ── │  config.json │
    │              │                  │              │
    │  perfil:     │                  │  perfil:     │
    │  darwin_mac  │                  │  linux_asus  │
    └──────────────┘                  └──────────────┘
```

**Una vía, dos trenes.** El mismo repo, el mismo JSON, la misma verdad. Cada máquina interpreta su perfil.

---

## Qué hacer si algo falla

1. **No toques el servidor directamente.** No hagas `mkdir`, no edites archivos a mano.
2. **Mira el log de validación.** `validate_config()` te dice qué paths faltan o no coinciden.
3. **Si falta un directorio**, o lo creas tú (una vez), o actualizas `system_config.json`.
4. **Si un modelo no está disponible**, actualizas la lista de modelos en el perfil correspondiente.
5. **Haz commit y push.** La próxima ejecución de mantenimiento hará `git pull` y aplicará los cambios.

---

*Versión 1.0 — 2026-06-03*
