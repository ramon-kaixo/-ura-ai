# ADR-011-01: Contrato de API de Plugins

> **Fecha:** 2026-07-05
> **Fase:** 11 (Plataforma)
> **Propósito:** Definir cómo los plugins declaran metadatos, dependencias, ciclo de vida y puntos de extensión.
> **Estado:** ✅ Aprobado

## Contexto

Fase 9 introdujo `PluginRegistry` con carga lazy y `PluginBase` abstracto. Sin
embargo, el sistema actual es minimalista:

- `PluginMeta` solo soporta `name`, `phase`, `blocking`, `timeout`, `description`
- No hay dependencias entre plugins
- No hay ciclo de vida explícito (`on_load`, `on_unload`)
- No hay puntos de extensión más allá de `execute(context)`
- No hay formato de paquete — un plugin es un solo `.py`

Para que F11 cumpla su objetivo de plataforma extensible, el contrato de API
debe ser estable, versionado y suficiente para que terceros desarrollen plugins
sin modificar el núcleo.

## Decisión

### 1. Formato de Paquete

Cada plugin es un **directorio** con:

```
my-plugin/
  plugin.yaml        ← metadatos declarativos (obligatorio)
  __init__.py        ← código del plugin (opcional si plugin.yaml define entry_point)
  hooks/             ← hooks opcionales, uno por archivo
    pre_ingest.py
    post_search.py
  assets/            ← recursos estáticos (opcional)
  README.md          ← documentación (opcional)
```

### 2. plugin.yaml

```yaml
# plugin.yaml — Metadatos del plugin
api_version: "1.0"                  # Versión del contrato de plugins
name: "my-plugin"
version: "1.2.3"
description: "Descripción breve"

author:
  name: "Autor"
  email: "author@example.com"

# Punto de entrada: clase que implementa PluginBase
entry_point: "MyPlugin"

# Dependencias (opcional)
dependencies:
  plugins:
    - name: "base-plugin"
      version: ">=1.0.0"
  python:
    - "requests>=2.28"

# Ciclo de vida (opcional — defaults: todos True)
lifecycle:
  on_load: true
  on_unload: true
  on_config_change: false

# Puntos de extensión (opcional)
hooks:
  - "pre_ingest"
  - "post_search"

# Fases del pipeline donde participa (opcional — defaults: ["always"])
phases:
  - "pre"
  - "post"

# Etiquetas para búsqueda y categorización
tags:
  - "seguridad"
  - "auditoria"
```

### 3. PluginBase Mejorado

```python
class PluginBase(ABC):
    """Clase base para todos los plugins F11+.

    Uso mínimo:
        class MyPlugin(PluginBase):
            def execute(self, context):
                return {"result": "ok"}
    """

    # ── Metadatos (inyectados por PluginRegistry tras parsear plugin.yaml) ──
    manifest: PluginManifest

    # ── Ciclo de vida (hooks opcionales) ────────────────────────────────────

    def on_load(self) -> None:
        """Inicialización. Se llama una vez al cargar el plugin."""

    def on_unload(self) -> None:
        """Limpieza. Se llama al descargar el plugin."""

    def on_config_change(self, old: dict, new: dict) -> None:
        """Se llama si la configuración del sistema cambia en caliente."""

    # ── Ejecución principal ─────────────────────────────────────────────────
    @abstractmethod
    def execute(self, context: dict | None = None) -> dict:
        """Ejecuta la lógica del plugin."""

    # ── Hooks de eventos (suscriptores EventBus) ────────────────────────────
    # Se registran automáticamente si el plugin los implementa.
    # El nombre del método define el tópico al que se suscribe.

    def on_pre_ingest(self, event: Event) -> None: ...
    def on_post_search(self, event: Event) -> Event | None: ...
```

### 4. PluginManifest

```python
@dataclass
class PluginManifest:
    api_version: str = "1.0"
    name: str = ""
    version: str = "0.1.0"
    description: str = ""
    author: dict = field(default_factory=dict)
    entry_point: str = ""
    dependencies: dict = field(default_factory=dict)
    lifecycle: dict = field(default_factory=lambda: {"on_load": True, "on_unload": True})
    hooks: list = field(default_factory=list)
    phases: list = field(default_factory=lambda: ["always"])
    tags: list = field(default_factory=list)
```

### 5. Contrato de Contexto

El `context` pasado a `execute()` es un dict inmutable (copia protegida) que
contiene como mínimo:

```python
{
    "config": {...},           # UraConfig serializado
    "state": {...},            # DegradedMode.status()
    "eventbus": EventBus,      # Referencia opcional al bus
    "dry_run": False,          # Modo simulación
    "plugin_dir": "/path",     # Directorio del plugin (para assets)
}
```

Los plugins NO deben mutar el context. Si necesitan estado compartido, usar
`EventBus.publish()`.

## Consecuencias

### Positivas
- Contrato estable permite desarrollo de plugins por terceros
- plugin.yaml autodescriptivo facilita depuración
- Ciclo de vida explícito evita fugas de recursos
- Hooks desacoplados via EventBus

### Negativas
- plugin.yaml añade fricción vs el .py suelto actual
- Migración de plugins existentes requiere wrapper
- Validación de plugin.yaml añade carga en Registry._load()

## Compatibilidad

- Esta ADR NO modifica `PluginBase` existente en `motor/plugin/base.py`
- Plugins F9 (solo .py) siguen funcionando via wrapper
- `PluginRegistry` existente convive con el nuevo `PluginRegistryV2`

## Migración

1. Crear `motor/plugin/manifest.py` con `PluginManifest` y `parse_manifest()`
2. Extender `PluginMeta` para incluir `manifest: PluginManifest | None`
3. Añadir `plugin.yaml` parser basado en YAML + schema validation
4. Crear `PluginRegistryV2` que maneja ambos formatos (legacy .py y plugin.yaml)
