# Provider Extension Guide

**Documento:** `docs/architecture/PROVIDER_EXTENSION_GUIDE.md`  
**Versión:** v1.0  
**Fecha:** 2026-07-16  
**Estado:** ✅ Activo

## 1. Introducción

Este documento define el contrato interno para añadir nuevos proveedores LLM
al sistema. Todo proveedor debe implementar exactamente la interfaz definida
en `motor/core/llm/base.py` para ser compatible con el Registry, Router y
los 8 consumidores existentes.

## 2. Contrato: `BaseLLMProvider`

Todo proveedor debe heredar de `BaseLLMProvider` e implementar los 4 métodos
abstractos:

| Método | Firma | Retorno | Descripción |
|--------|-------|---------|-------------|
| `generate` | `(prompt: str, model: str \| None = None, options: dict \| None = None) -> str` | Texto generado | Generación de texto |
| `embed` | `(texts: list[str], model: str \| None = None) -> list[list[float]]` | Vectores de embedding | Embeddings síncronos |
| `embed_async` | `(texts: list[str], model: str \| None = None) -> list[list[float]]` | Vectores de embedding | Embeddings asíncronos |
| `health` | `() -> dict[str, Any]` | Estado del proveedor | Health check |

### 2.1 Reglas de implementación

1. **Sin excepciones**: Todos los errores deben capturarse internamente y
   traducirse a respuestas con prefijo `"Error:"` (generate) o vectores de
   relleno (embed).
2. **Thread-safe**: El proveedor debe ser seguro para uso concurrente.
3. **Sin estado compartido**: No debe modificar estado global más allá de
   su propia instancia.
4. **Configuración**: Los parámetros de configuración deben obtenerse vía
   `motor.core.secrets.get_secret()` o `CONFIG` (config_manager).

### 2.2 Campos de instancia requeridos

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `_provider_name` | `str` | Identificador único del proveedor |

## 3. Lifecycle

```
Instanciación → registro en Registry → uso via Router → (sin destructor explícito)
```

1. **Instanciación**: El proveedor se instancia con configuración de
   `secrets` y/o `CONFIG`.
2. **Registro**: Se registra en `ProviderRegistry` con un nombre único.
3. **Selección**: El `LLMRouter` selecciona el proveedor según rutas o
   petición explícita.
4. **Uso**: Las llamadas pasan por Circuit Breaker + Retry + Fallback
   (ver F19).
5. **Health**: `health()` se llama periódicamente vía health cache del
   router.

## 4. Health Contract

`health()` debe retornar un dict con al menos:

```python
{
    "provider": str,      # Nombre del proveedor
    "status": str,        # "ok" o "error"
    "latency_ms": float,  # Tiempo de respuesta
}
```

En caso de éxito, puede incluir claves adicionales como `modelos_disponibles`.

## 5. Capabilities

Los proveedores pueden declarar capacidades opcionales. No hay un sistema
formal de capabilities más allá de implementar los 4 métodos del contrato.

| Capacidad | Método | Descripción |
|-----------|--------|-------------|
| Generación | `generate` | Generación de texto |
| Embeddings | `embed`, `embed_async` | Generación de vectores |
| Health check | `health` | Disponibilidad del servicio |

## 6. Configuración

### 6.1 Secretos (recomendado)

Usar `motor.core.secrets` para API keys y tokens:

```python
from motor.core.secrets import get_secret, require_secret

class MiProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._provider_name = "miprovedor"
        self._api_key = require_secret("MI_PROVIDER_API_KEY")
        self._base_url = get_secret("MI_PROVIDER_BASE_URL", "https://api.default.com")
```

### 6.2 ConfigManager (fallback)

```python
from core.config_manager import CONFIG

class MiProvider(BaseLLMProvider):
    def __init__(self) -> None:
        cfg = CONFIG.get("llm", {}).get("providers", {}).get("miprovedor", {})
        self._model = cfg.get("model", "default-model")
```

## 7. Errores Soportados

| Tipo de error | HTTP | Es transitorio? | Se reintenta? | Afecta CB? |
|--------------|------|-----------------|---------------|------------|
| Timeout | — | ✅ Sí | ✅ Sí | ✅ Sí |
| Connection error | — | ✅ Sí | ✅ Sí | ✅ Sí |
| Rate limit | 429 | ✅ Sí | ✅ Sí | ✅ Sí |
| Server error | 5xx | ✅ Sí | ✅ Sí | ✅ Sí |
| Bad request | 400 | ❌ No | ❌ No | ❌ No |
| Unauthorized | 401 | ❌ No | ❌ No | ❌ No |
| Forbidden | 403 | ❌ No | ❌ No | ❌ No |
| Not found | 404 | ❌ No | ❌ No | ❌ No |
| Validation error | — | ❌ No | ❌ No | ❌ No |

## 8. Validación Automática

Usar `motor.core.llm.base.validate_provider()` para verificar que un
proveedor cumple el contrato:

```python
from motor.core.llm.base import validate_provider, ProviderValidationResult

result = validate_provider(MiProvider)
if result.valid:
    print(f"Proveedor válido: {result.provider_name}")
else:
    print(f"Errores: {result.errors}")
```

## 9. Checklist de Implementación

- [ ] Heredar de `BaseLLMProvider`
- [ ] Implementar `generate(prompt, model=None, options=None) -> str`
- [ ] Implementar `embed(texts, model=None) -> list[list[float]]`
- [ ] Implementar `embed_async(texts, model=None) -> list[list[float]]`
- [ ] Implementar `health() -> dict`
- [ ] Definir `_provider_name`
- [ ] Capturar todas las excepciones → respuestas con prefijo `"Error:"`
- [ ] Usar `motor.core.secrets` para API keys
- [ ] Ejecutar `validate_provider(MiProvider)` → `valid=True`
- [ ] Registrar en `motor/core/llm/__init__.py` (en el bloque `if provider_name == "nuevo"`)
- [ ] Añadir configuración en `config.local.json` (`llm.providers.nuevo.*`)
- [ ] Ejecutar `pytest` — 0 regresiones

## 10. Ejemplo: Provider Mínimo

```python
from typing import Any
from motor.core.llm.base import BaseLLMProvider

class MiProvider(BaseLLMProvider):
    def __init__(self) -> None:
        self._provider_name = "miprovedor"

    def generate(self, prompt: str, model: str | None = None,
                 options: dict | None = None) -> str:
        try:
            # ... llamada HTTP a la API ...
            return "respuesta"
        except Exception:
            return "Error: No se pudo generar."

    def embed(self, texts: list[str], model: str | None = None
              ) -> list[list[float]]:
        try:
            return [[0.0] * 768 for _ in texts]
        except Exception:
            return [[0.0] * 768]

    async def embed_async(self, texts: list[str], model: str | None = None
                          ) -> list[list[float]]:
        return self.embed(texts, model)

    def health(self) -> dict[str, Any]:
        return {"provider": self._provider_name, "status": "ok", "latency_ms": 0}
```
