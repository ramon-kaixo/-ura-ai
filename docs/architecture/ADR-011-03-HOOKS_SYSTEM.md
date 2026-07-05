# ADR-011-03: Sistema de Hooks Desacoplado del Núcleo

> **Fecha:** 2026-07-05
> **Fase:** 11 (Plataforma)
> **Propósito:** Definir el sistema de hooks que permite a plugins y
> extensiones interceptar y modificar el flujo del motor sin tocar el núcleo.
> **Estado:** ✅ Aprobado

## Contexto

Hasta F10, las extensiones del sistema requerían modificar el código del motor
(`motor/`) o envolverlo con scripts externos. F11 introduce hooks como puntos
de extensión formales donde plugins pueden:

- **Inspeccionar** eventos sin modificar el flujo (observabilidad)
- **Interceptar** y modificar datos antes de que lleguen a su destino
- **Cancelar** operaciones en curso

Los hooks NO deben requerir modificar el núcleo (`core/`). Deben registrarse y
ejecutarse a través del EventBus.

## Decisión

### 1. Arquitectura

Los hooks son **suscriptores EventBus especializados** que se registran
automáticamente cuando un plugin se carga.

```
Plugin.on_load()
  → PluginRegistry registra hooks del plugin en EventBus
  → EventBus.emit_sync("plugin.hook.pre_ingest", payload)
  → Cada subscriptor devuelve datos modificados o None (no-op)
  → PluginRegistry verifica que ningún hook haya fallado
```

### 2. Tipos de Hooks

#### a) Hooks de Pipeline

```python
# Firma: (event: Event) -> Event | None
# Si retorna None, se cancela la operación.
# Si retorna Event con payload modificado, se usa el modificado.

HOOK_PIPELINE = {
    "pre_ingest":    "(event) -> Event | None",   # filtrar/modificar docs antes de indexar
    "post_ingest":   "(event) -> Event | None",   # post-procesar docs indexados
    "pre_search":    "(event) -> Event | None",   # modificar consulta antes de buscar
    "post_search":   "(event) -> Event | None",   # filtrar/rerankear resultados
    "pre_index":     "(event) -> Event | None",   # modificar chunk antes de vectorizar
    "post_index":    "(event) -> Event | None",   # post-procesar vectores indexados
}
```

#### b) Hooks de Sistema

```python
HOOK_SYSTEM = {
    "on_startup":    "(event) -> None",            # inicialización
    "on_shutdown":   "(event) -> None",            # limpieza
    "on_degraded":   "(event) -> None",            # notificación degradación
    "on_restore":    "(event) -> Event | None",    # puede cancelar restauración
}
```

#### c) Hooks de CLI

```python
HOOK_CLI = {
    "pre_command":   "(event) -> Event | None",    # validar/modificar args antes de ejecutar
    "post_command":  "(event) -> None",            # post-procesar resultado del comando
}
```

### 3. Registro Automático

En `PluginRegistry._load()`, después de instanciar el plugin:

```python
for hook_name in plugin.manifest.hooks:
    if hasattr(plugin, f"on_{hook_name}"):
        topic = f"plugin.hook.{hook_name}"
        self._eventbus.subscribe(topic, getattr(plugin, f"on_{hook_name}"))
```

### 4. Cadena de Hooks

Los hooks del mismo tópico se ejecutan en **serie** (orden de registro):

```
emit_sync("plugin.hook.pre_ingest", doc)
  → hook_a.on_pre_ingest(doc) → doc_modificado
  → hook_b.on_pre_ingest(doc_modificado) → doc_final
  → retorna doc_final
```

Si un hook retorna `None`, la cadena se interrumpe y la operación se cancela.

### 5. Fallo de Hooks

- Un hook que lanza excepción NO afecta a otros hooks
- La excepción se registra en DegradedMode: `self._dm.mark_degraded(f"hook:{name}")`
- El hook se desuscribe automáticamente tras N fallos consecutivos (circuit breaker: 3 intentos)

### 6. Hooks vs Eventos

| Aspecto | Hook | Evento |
|---------|------|--------|
| Propósito | Modificar flujo | Notificar |
| Tipo | `emit_sync` (bloqueante) | `publish` / `publish_async` |
| Retorno | `Event | None` | `None` |
| Encadenamiento | Serie, ordenado | Paralelo (async) |
| Cancelación | Retornando None | No aplica |

## Consecuencias

### Positivas
- Hooks completamente desacoplados del núcleo
- Reutilizan EventBus (no hay infraestructura nueva)
- Circuit breaker evita que un hook malo degrade el sistema
- Cadena de hooks permite composición

### Negativas
- Hooks síncronos añaden latencia al pipeline
- Circuit breaker puede silenciar errores legítimos
- Depuración de cadenas de hooks largas puede ser compleja

## Compatibilidad

- No requiere cambios en `core/`
- `PluginBase` existente sigue funcionando sin hooks
- Hooks son opt-in: plugin sin hooks = mismo comportamiento que F9/F10

## Migración

1. Implementar `motor/events/hooks.py` con los diccionarios de hooks predefinidos
2. Añadir registro automático en `PluginRegistry._load()`
3. Implementar circuit breaker en `motor/events/circuit_breaker.py`
4. Escribir tests: cadena de hooks, cancelación, fallo aislado, circuit breaker
