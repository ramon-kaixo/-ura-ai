# Plugin API — URA Platform v1.0

> **API Version:** `1.0.0`
> **Status:** Draft (Fase 11)
> **Última actualización:** 2026-07-05

---

## 1. Introducción

La Plugin API permite extender el motor URA sin modificar el núcleo.
Los plugins pueden:

- Participar en pipelines de ingesta y búsqueda
- Reaccionar a eventos del sistema (startup, shutdown, degradación)
- Interceptar y modificar comandos CLI
- Exportar métricas y estado

---

## 2. Estructura de un Plugin

```
my-plugin/
├── plugin.yaml          ← Metadatos (obligatorio)
├── __init__.py          ← Código (obligatorio)
├── hooks/               ← Hooks opcionales
│   ├── pre_ingest.py
│   └── post_search.py
├── assets/              ← Recursos estáticos
└── README.md            ← Documentación
```

---

## 3. plugin.yaml

```yaml
api_version: "1.0.0"
name: "my-plugin"
version: "1.2.3"
description: "Descripción del plugin"

author:
  name: "Tu Nombre"
  email: "tu@email.com"

entry_point: "MyPlugin"

dependencies:
  plugins:
    - name: "base-plugin"
      version: ">=1.0.0"
  python:
    - "requests>=2.28"

lifecycle:
  on_load: true
  on_unload: true
  on_config_change: false

hooks:
  - "pre_ingest"
  - "post_search"

phases:
  - "pre"
  - "post"

tags:
  - "seguridad"
  - "auditoria"
```

### Campos

| Campo | Tipo | Obligatorio | Default | Descripción |
|-------|------|-------------|---------|-------------|
| `api_version` | string | sí | — | Versión de la Plugin API contra la que se desarrolló |
| `name` | string | sí | — | Identificador único del plugin (snake_case) |
| `version` | string | sí | `0.1.0` | Versión SemVer del plugin |
| `description` | string | no | `""` | Descripción breve |
| `author` | dict | no | `{}` | `{name, email, url}` |
| `entry_point` | string | no | `None` | Clase que implementa `PluginBase` |
| `dependencies.plugins` | list | no | `[]` | Dependencias entre plugins |
| `dependencies.python` | list | no | `[]` | Dependencias pip |
| `lifecycle` | dict | no | `{on_load: true, on_unload: true}` | Hooks de ciclo de vida |
| `hooks` | list | no | `[]` | Puntos de extensión |
| `phases` | list | no | `["always"]` | Fases del pipeline |
| `tags` | list | no | `[]` | Etiquetas para búsqueda |

---

## 4. PluginBase

### API completa

```python
from motor.plugin.base import PluginBase, PluginManifest
from motor.events.bus import Event


class MyPlugin(PluginBase):
    """Plugin de ejemplo."""

    # ── Metadatos (inyectados por PluginRegistry) ──
    manifest: PluginManifest

    # ── Ciclo de vida ───────────────────────────────

    def on_load(self) -> None:
        self.client = MyExternalClient()

    def on_unload(self) -> None:
        self.client.close()

    def on_config_change(self, old: dict, new: dict) -> None:
        self.client.reconfigure(new)

    # ── Ejecución principal ─────────────────────────

    def execute(self, context: dict | None = None) -> dict:
        return {"result": "ok", "data": self.client.fetch()}

    # ── Hooks de eventos ────────────────────────────
    # Se registran automáticamente según manifest.hooks

    def on_pre_ingest(self, event: Event) -> Event | None:
        doc = event.payload.document
        if doc.get("sensitive"):
            return None  # cancela la operación
        doc["processed"] = True
        return Event(event.topic, doc, event.timestamp, event.source, event.id)

    def on_post_search(self, event: Event) -> Event | None:
        results = event.payload.results
        results.sort(key=lambda r: r["score"], reverse=True)
        return Event(event.topic, results, event.timestamp, event.source, event.id)
```

### Métodos

| Método | Retorno | Obligatorio | Descripción |
|--------|---------|-------------|-------------|
| `execute(context)` | `dict` | **sí** | Lógica principal del plugin |
| `on_load()` | `None` | no | Inicialización al cargar |
| `on_unload()` | `None` | no | Limpieza al descargar |
| `on_config_change(old, new)` | `None` | no | Reconfiguración en caliente |
| `on_<hook>(event)` | `Event \| None` | no | Hooks registrados en manifest |

### Contexto

El dict `context` pasado a `execute()` contiene:

```python
{
    "config": {...},             # UraConfig serializado (solo lectura)
    "state": {...},              # DegradedMode.status()
    "eventbus": EventBus,        # Referencia al bus (opcional)
    "dry_run": False,            # Modo simulación
    "plugin_dir": "/path/to/plugin",  # Directorio del plugin
    "logger": logging.Logger,    # Logger con nombre del plugin
}
```

**Regla:** No mutar el context. Usar EventBus para estado compartido.

---

## 5. EventBus

### API

```python
from motor.events.bus import EventBus
from motor.events.topics import (
    SYSTEM_STARTED, SYSTEM_SHUTDOWN,
    PIPELINE_STARTED, PIPELINE_COMPLETED, PIPELINE_FAILED,
    PLUGIN_LOADED, PLUGIN_UNLOADED, PLUGIN_ERROR,
    CONFIG_CHANGED,
)
from motor.events.payloads import (
    SystemStarted, SystemShutdown,
    PipelineStarted, PipelineCompleted, PipelineFailed,
    PluginLoaded, PluginUnloaded, PluginError,
    HookEvent,
)

bus = EventBus()

# Publicar
bus.publish(SYSTEM_STARTED, SystemStarted(python_version="3.12", ura_version="0.11.0"))
bus.publish_async(PIPELINE_COMPLETED, PipelineCompleted(name="ingest", result=results))

# Hooks síncronos (modifican flujo)
modified = bus.emit_sync("plugin.hook.pre_ingest", doc_event)

# Suscribir
sid = bus.subscribe("pipeline.*", my_callback, pattern=True)
bus.unsubscribe(sid)
```

### Tópicos Predefinidos

Ver `motor/events/topics.py` para la lista completa. Los tópicos siguen
el formato `dominio.accion` (ej. `system.started`, `pipeline.failed`).

### Patrones

Los patrones glob permiten suscripción a múltiples tópicos:

| Patrón | Matches |
|--------|---------|
| `pipeline.*` | `pipeline.started`, `pipeline.completed`, `pipeline.failed` |
| `plugin.*` | `plugin.loaded`, `plugin.unloaded`, `plugin.error` |
| `*.failed` | `pipeline.failed`, `plugin.error` |
| `system.*` | `system.started`, `system.shutdown`, `system.degraded` |

---

## 6. Hooks

### Hooks de Pipeline

| Hook | Momento | Efecto de retornar None |
|------|---------|------------------------|
| `pre_ingest` | Antes de indexar un documento | El documento se omite |
| `post_ingest` | Después de indexar | No afecta al índice |
| `pre_search` | Antes de ejecutar búsqueda | La búsqueda se cancela |
| `post_search` | Después de obtener resultados | Resultados filtrados/rerankeados |
| `pre_index` | Antes de vectorizar un chunk | El chunk se omite |
| `post_index` | Después de vectorizar | No afecta al índice |

### Hooks de Sistema

| Hook | Momento | Efecto de retornar None |
|------|---------|------------------------|
| `on_startup` | Motor iniciado | — |
| `on_shutdown` | Motor apagándose | — |
| `on_degraded` | Subsistema degradado | — |
| `on_restore` | Subsistema recuperado | Cancela la restauración |

### Hooks de CLI

| Hook | Momento | Efecto de retornar None |
|------|---------|------------------------|
| `pre_command` | Antes de ejecutar comando | El comando no se ejecuta |
| `post_command` | Después de ejecutar comando | — |

### Circuit Breaker

Si un hook lanza excepción 3 veces consecutivas, se desuscribe automáticamente
y se marca en DegradedMode.

---

## 7. Versionado

### Compatibilidad Motor ↔ Plugin

```yaml
# plugin.yaml
api_version: "1.0.0"    # Plugin desarrollado contra API v1.0.0
```

El motor acepta plugins cuyo `api_version` esté dentro de su matriz de
compatibilidad. La matriz actual:

| Motor API | Min Plugin API | Max Plugin API |
|-----------|---------------|----------------|
| `1.0.x` | `1.0.0` | `1.x` |
| `1.1.x` | `1.0.0` | `1.x` |

### Dependencias entre Plugins

```yaml
dependencies:
  plugins:
    - name: "base-plugin"
      version: ">=1.0.0 <2.0.0"
```

El rango usa notación SemVer estándar: `>=1.0.0`, `<2.0.0`, `~=1.0.0`, `==1.2.3`.

---

## 8. Plugin SDK

El SDK mínimo está en `motor/plugin/` e incluye:

| Archivo | Contenido |
|---------|-----------|
| `base.py` | `PluginBase`, `PluginManifest` |
| `registry.py` | `PluginRegistry` (carga, descarga, enable/disable) |
| `manifest.py` | Parseo y validación de `plugin.yaml` |

### Instalación de un Plugin

```bash
python3 ura.py plugin install ./my-plugin
python3 ura.py plugin list
python3 ura.py plugin enable my-plugin
python3 ura.py plugin disable my-plugin
python3 ura.py plugin uninstall my-plugin
```

---

## 9. Buenas Prácticas

1. **Un plugin, una responsabilidad.** No hagas un plugin que indexe y también
   envíe notificaciones.
2. **Sé tolerante a fallos.** Si tu dependencia Python no está instalada, no
   impidas la carga del plugin — degrada.
3. **Usa EventBus para comunicación.** No importes otros plugins directamente.
4. **Documenta tu plugin.yaml.** Los campos `description` y `tags` se usan
   en `ura.py plugin search`.
5. **Respeta el contexto.** No mutes `context` ni almacenes referencias
   prolongadas a él.
6. **Cierra recursos en `on_unload()`.** Conexiones HTTP, archivos temporales,
   hilos.
7. **Prueba tu plugin.** Usa `pytest` con el fixture `plugin_registry` que
   proporciona el SDK.

---

## 10. Referencia Rápida

```python
# plugin mínimo
from motor.plugin.base import PluginBase

class MyPlugin(PluginBase):
    def execute(self, context):
        return {"hello": "world"}
```

```yaml
# plugin.yaml mínimo
api_version: "1.0.0"
name: "my-plugin"
version: "0.1.0"
entry_point: "MyPlugin"
```
