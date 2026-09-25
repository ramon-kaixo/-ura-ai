# ADR-011-04: Versionado y Compatibilidad de Plugins

> **Fecha:** 2026-07-05
> **Fase:** 11 (Plataforma)
> **Propósito:** Definir el esquema de versionado para plugins, API del motor
> y matriz de compatibilidad entre versiones.
> **Estado:** ✅ Aprobado

## Contexto

A medida que F11 convierte el motor en una plataforma extensible, múltiples
plugins de diferentes autores convivirán en el mismo sistema. Sin un sistema
de versionado, un plugin escrito para API v1.0 podría romper silenciosamente
al cargarse en un motor que ya implementa API v2.0.

Se necesita:
- Versionado semántico para plugins y API del motor
- Matriz de compatibilidad explícita
- Mecanismo de rechazo en carga si hay incompatibilidad

## Decisión

### 1. Versionado Semántico (SemVer 2.0)

Todos los plugins y la API del motor usan SemVer estricto: `MAJOR.MINOR.PATCH`.

| Componente | SemVer | Quién incrementa |
|------------|--------|------------------|
| `api_version` del motor | motor define su API version | Mantenedores del motor |
| `version` del plugin | autor del plugin | Desarrollador del plugin |

### 2. api_version del Motor

El motor expone su API version en `motor/__init__.py`:

```python
# motor/__init__.py
PLUGIN_API_VERSION = "1.0.0"  # SemVer
```

Reglas de incremento:

| Cambio en el motor | api_version |
|--------------------|-------------|
| Nueva funcionalidad backward-compatible | MINOR+1, PATCH=0 |
| Bugfix en API existente (sin cambio de interfaz) | PATCH+1 |
| Breaking change en API de plugins | MAJOR+1, MINOR=0, PATCH=0 |

### 3. Matriz de Compatibilidad

La compatibilidad se define como:

```python
# motor/events/compat.py
COMPATIBILITY_MATRIX = {
    "1.0.x": {"min_plugin_api": "1.0.0", "max_plugin_api": "1.x"},
    "1.1.x": {"min_plugin_api": "1.0.0", "max_plugin_api": "1.x"},
    "2.0.0": {"min_plugin_api": "2.0.0", "max_plugin_api": "2.x"},
}
```

Reglas:
- Motor con api_version `X.Y.Z` acepta plugins con `api_version` en el rango
  `[min_plugin_api, max_plugin_api]`
- `max_plugin_api` en formato `MAJOR.x` significa "cualquier MINOR/PATCH dentro de MAJOR"
- Si un plugin declara `api_version` fuera del rango → PluginRegistry rechaza la carga
  con error `IncompatibleAPIVersion`

### 4. Declaración en plugin.yaml

```yaml
api_version: "1.0.0"     # ← contra qué versión del motor fue desarrollado
name: "my-plugin"
version: "1.2.3"         # ← versión del plugin (SemVer)

# Dependencias entre plugins
dependencies:
  plugins:
    - name: "base-plugin"
      version: ">=1.0.0 <2.0.0"    # Rango SemVer
```

### 5. Resolución de Dependencias

Al cargar un plugin:

```
1. Validar api_version del plugin vs matriz de compatibilidad del motor
   → si incompatible: PluginError("Plugin requiere API v2.x, motor tiene v1.x")

2. Validar dependencias de plugins:
   a. Buscar cada dependencia en _entries
   b. Verificar que la versión instalada satisface el rango
   c. Si no: cargar dependencia primero (orden topológico)

3. Validar dependencias Python:
   a. Verificar que los paquetes están instalados
   b. Si no: log.warning (no blocker — el plugin puede fallar en execute)
```

### 6. Rechazo (Rejection) vs Degradación

| Escenario | Acción |
|-----------|--------|
| api_version incompatible | **Rechazar**: no cargar, error claro |
| Dependencia plugin no encontrada | **Degradar**: cargar pero marcar en DegradedMode |
| Dependencia plugin versión incorrecta | **Degradar**: cargar pero log.warning |
| Dependencia Python no instalada | **Degradar**: cargar, fallará en execute() |

### 7. Compatibilidad hacia atrás

Los plugins escritos para el sistema F9 (sin plugin.yaml, solo PluginBase)
se consideran implícitamente como `api_version: "0.9.0"`. La matriz de
compatibilidad los acepta con una advertencia:

```python
# Legacy F9 plugin → compatibilidad implícita
if manifest is None:
    log.warning("Plugin %s sin plugin.yaml — compatibilidad legacy F9", name)
    return True  # permitir carga
```

## Consecuencias

### Positivas
- Contrato claro entre motor y plugins
- Los plugins fallan en carga con error comprensible, no en ejecución
- Dependencias explícitas evitan conflictos silenciosos
- Legacy F9 sigue funcionando

### Negativas
- Validación de dependencias añade latencia a carga de plugins (~5-10ms)
- Matriz de compatibilidad debe mantenerse manualmente
- Plugins con dependencias circulares requieren detección

## Compatibilidad

- Plugins F9/F10 existentes: aceptados con advertencia
- API version del motor: `"1.0.0"` para F11, revisada en cada release

## Migración

1. Implementar `motor/events/compat.py` con `COMPATIBILITY_MATRIX` y `validate()`
2. Integrar validación en `PluginRegistry._load()`
3. Detección de dependencias circulares (DFS)
4. Tests: compat OK, incompat rechazada, legacy F9, circular detection
