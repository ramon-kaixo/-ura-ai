# LLM API — Contrato Público Congelado

**Documento:** `docs/architecture/LLM_API.md`  
**Versión:** v1.0 (A1)  
**Fecha:** 2026-07-16  
**Estado:** ✅ Congelado  

## 1. Propósito

Este documento define el contrato público del módulo `motor.core.llm`.
Cualquier cambio en lo aquí especificado requiere un ADR (Architecture Decision Record)
y una nueva versión del contrato.

## 2. API Pública

El módulo exporta exactamente **4 funciones** en `__all__`:

| Función | Import | Propósito |
|---------|--------|-----------|
| `generate` | `from motor.core.llm import generate` | Generación de texto |
| `embed` | `from motor.core.llm import embed` | Embeddings síncronos |
| `embed_async` | `from motor.core.llm import embed_async` | Embeddings asíncronos |
| `health` | `from motor.core.llm import health` | Health check del proveedor activo |

### 2.1 `generate`

```python
def generate(
    prompt: str,
    model: str | None = None,
    options: dict | None = None,
) -> str
```

**Parámetros:**
| Nombre | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `prompt` | `str` | (requerido) | Texto de entrada para el modelo |
| `model` | `str \| None` | `None` | Nombre del modelo. `None` = usar default del proveedor |
| `options` | `dict \| None` | `None` | Opciones del modelo (temperature, num_predict, etc.). `None` = usar default del proveedor |

**Retorno:** `str` — texto generado. En caso de error, retorna un mensaje con prefijo `"Error:"`.

**Excepciones:** No lanza excepciones. Todos los errores se traducen a respuestas con prefijo `"Error:"`.

**Uso típico:**
```python
generate("¿Qué es RAG?")
generate("Explica X", model="qwen2.5:7b")
generate("Refactoriza esto", model="gpt-4", options={"temperature": 0.0, "max_tokens": 4096})
```

### 2.2 `embed`

```python
def embed(
    texts: list[str],
    model: str | None = None,
) -> list[list[float]]
```

**Parámetros:**
| Nombre | Tipo | Default | Descripción |
|--------|------|---------|-------------|
| `texts` | `list[str]` | (requerido) | Lista de textos a vectorizar |
| `model` | `str \| None` | `None` | Nombre del modelo de embeddings. `None` = usar default del proveedor |

**Retorno:** `list[list[float]]` — lista de vectores, uno por texto de entrada. En caso de error, retorna vectores de relleno (`[0.0] * 768` o `[0.0] * 1536`).

**Excepciones:** No lanza excepciones. Fallback a embedding individual si el batch falla.

**Uso típico:**
```python
embed(["texto1", "texto2"])
embed(["texto"], model="nomic-embed-text")
```

### 2.3 `embed_async`

```python
async def embed_async(
    texts: list[str],
    model: str | None = None,
) -> list[list[float]]
```

**Parámetros:** Idéntico a `embed()`.

**Retorno:** Idéntico a `embed()`.

**Excepciones:** No lanza excepciones.

**Uso típico:**
```python
vectores = await embed_async(textos, model="nomic-embed-text")
```

### 2.4 `health`

```python
def health() -> dict[str, Any]
```

**Parámetros:** Ninguno.

**Retorno:** `dict` con al menos las claves:
```python
{
    "provider": str,      # Nombre del proveedor ("ollama", "openai", ...)
    "status": str,        # "ok" o "error"
    "latency_ms": float,  # Tiempo de respuesta en milisegundos
}
```

En caso de éxito (`status == "ok"`), puede incluir claves adicionales:
```python
{
    "modelos_disponibles": list[str],  # Solo proveedores que listan modelos
}
```

**Excepciones:** No lanza excepciones. En caso de error de conexión, retorna `{"status": "error", ...}`.

**Uso típico:**
```python
estado = health()
if estado["status"] == "ok":
    print("Servicio disponible")
```

## 3. Proveedores

### 3.1 `BaseLLMProvider`

Clase abstracta base que todo proveedor debe implementar.

```python
class BaseLLMProvider(ABC):
    @abstractmethod
    def generate(self, prompt: str, model: str | None = None, options: dict | None = None) -> str: ...
    @abstractmethod
    def embed(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...
    @abstractmethod
    async def embed_async(self, texts: list[str], model: str | None = None) -> list[list[float]]: ...
    @abstractmethod
    def health(self) -> dict[str, Any]: ...
```

**Ubicación:** `motor/core/llm/base.py`

### 3.2 `OllamaProvider`

Proveedor por defecto. Conecta con Ollama vía API HTTP.

**Configuración:** `CONFIG["llm"]` + `CONFIG["ollama"]` + `CONFIG["rag"]` (fallback encadenado).

**Ubicación:** `motor/core/llm/ollama.py`

### 3.3 `OpenAIProvider`

Proveedor compatible con OpenAI API. Requiere `OPENAI_API_KEY` en secretos.

**Configuración:** Variables de entorno / `/etc/ura/secrets.env` vía `motor.core.secrets`.

**Ubicación:** `motor/core/llm/openai.py`

## 4. Registry

```python
from motor.core.llm.registry import ProviderRegistry, registry
```

**API pública del registry:**
| Método | Firma | Descripción |
|--------|-------|-------------|
| `register` | `register(name: str, provider: BaseLLMProvider, *, default: bool = False) -> None` | Registra un proveedor |
| `unregister` | `unregister(name: str) -> None` | Elimina un proveedor |
| `get` | `get(name: str) -> BaseLLMProvider` | Obtiene por nombre (KeyError si no existe) |
| `list` | `list() -> dict[str, type[BaseLLMProvider]]` | Lista nombre → clase |
| `default` | `property -> BaseLLMProvider \| None` | Proveedor predeterminado |
| `default_name` | `property -> str \| None` | Nombre del predeterminado |

El singleton `registry` se puebla automáticamente al importar `motor.core.llm`.

## 5. Router

```python
from motor.core.llm.router import LLMRouter
```

**API pública del router:**
| Método | Firma | Descripción |
|--------|-------|-------------|
| `generate` | `generate(prompt, model=None, options=None, *, provider=None) -> str` | Genera con proveedor explícito |
| `embed` | `embed(texts, model=None, *, provider=None) -> list[list[float]]` | Embeddings con proveedor explícito |
| `embed_async` | `embed_async(texts, model=None, *, provider=None) -> list[list[float]]` | Embeddings async con proveedor explícito |
| `health` | `health(*, provider=None) -> dict[str, Any]` | Health check con proveedor explícito |

**Uso:**
```python
router = LLMRouter()
respuesta = router.generate("Hola", provider="ollama")
router2 = LLMRouter(routes={"generate": "openai"})
```

## 6. Consumidores (8 en producción)

| # | Archivo | Funciones | Modelo |
|---|---------|-----------|--------|
| 1 | `motor/core/qdrant_client.py` | `embed`, `embed_async` | Explícito (`nomic-embed-text`) |
| 2 | `motor/intelligence/reranking/llm.py` | `generate` | Explícito (`self._model`) + options |
| 3 | `motor/intelligence/memory/extractor_llm.py` | `generate` | Explícito (`self._model`) + options |
| 4 | `core/memory_engine.py` | `generate` | **Default del proveedor** |
| 5 | `core/debate/debate_engine.py` | `generate` (via `to_thread`) | Explícito + options |
| 6 | `core/ura_multi_agent.py` | `generate`, `health` | Explícito + options |
| 7 | `scripts/pro/benchmark_llm.py` | `generate`, `embed` | **Default del proveedor** |
| 8 | `knowledge/engine/vector_ollama.py` | `embed`, `health` | Explícito (`nomic-embed-text`) |

## 7. Reglas de Congelación

1. **No modificar firmas** de `generate`, `embed`, `embed_async`, `health`.
2. **No modificar comportamiento observable**: misma entrada → misma salida (modulo errores transitorios).
3. **No eliminar funciones** de `__all__`.
4. **Extensiones permitidas** sin ADR:
   - Nuevos métodos en `BaseLLMProvider` con implementación por defecto (no abstractos).
   - Nuevos parámetros con valor por defecto (`*` separador).
   - Nuevos proveedores que implementen `BaseLLMProvider`.
5. **Extensiones que requieren ADR**:
   - Cambio en firmas existentes.
   - Cambio en tipos de retorno.
   - Eliminación de funcionalidad.
