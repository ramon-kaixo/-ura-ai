# ADR-012-02: Memory Model — Episódica, Semántica, Working, Largo Plazo

> **Fecha:** 2026-07-05
> **Fase:** 12 (Inteligencia)
> **Propósito:** Definir formalmente los tipos de memoria, sus relaciones y contratos.
> **Estado:** ✅ Aprobado

## Contexto

Hasta ahora, URA no tiene un sistema de memoria unificado. Los agentes no
recuerdan interacciones pasadas, el contexto se pierde entre turnos, y no hay
diferenciación entre "lo que ocurrió" (episodios) y "lo que se sabe" (hechos).

F12 introduce memoria al sistema. Sin un modelo formal, cada componente
(EpisodicMemory, SemanticMemory, etc.) inventará su propia estructura,
haciendo imposible la integración futura con Multi-Agent Runtime y Consensus.

## Decisión

### 1. Tipos de Memoria

```
Working Memory (corto plazo, volátil)
    ↑ consolidación ↓
Episodic Memory (experiencias, secuencias)
    ↑ abstracción ↓
Semantic Memory (hechos, conocimiento)
    ↑ consolidación ↓
Long-Term Memory (persistente, indexado)
```

#### Working Memory
- Duración: sesión actual (volátil al reiniciar)
- Contenido: contexto activo, consulta actual, últimos N turnos
- Capacidad: configurable (default 50 episodios)
- Almacenamiento: en memoria (no persistente)

#### Episodic Memory
- Duración: persistente con TTL (default 7 días)
- Contenido: interacciones completas (query → respuesta → feedback)
- Estructura: secuencia de Episode con metadatos temporales
- Índice: embedding del contenido + timestamp + importancia

#### Semantic Memory
- Duración: persistente sin TTL (hasta olvido explícito)
- Contenido: hechos extraídos, deduplicados, versionados
- Estructura: hechos atómicos con confianza y fuente
- Índice: embedding del hecho + entidades referenciadas

#### Long-Term Memory
- Duración: permanente
- Contenido: KE index (documentos, vectores)
- No se implementa en este bloque (es el KE existente)

### 2. MemoryRecord — Contrato Unificado

```python
@dataclass
class MemoryRecord:
    id: str                          # UUID único
    type: MemoryType                 # EPISODIC | SEMANTIC | WORKING
    timestamp: str                   # ISO 8601
    source: str                      # agente o componente que lo creó
    importance: float                # 0.0 (insignificante) - 1.0 (crítico)
    confidence: float                # 0.0 (incierto) - 1.0 (confirmado)
    embedding: list[float] | None    # vector 768d (nomic-embed-text)
    tags: list[str]                  # etiquetas para búsqueda
    references: list[str]            # IDs de registros relacionados
    ttl: int | None                  # segundos hasta expiración (None = permanente)
    metadata: dict                   # metadatos específicos del tipo
    payload: str                     # contenido textual

class MemoryType(Enum):
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
```

### 3. APIs Públicas

```python
class MemoryStore(ABC):
    @abstractmethod
    def store(self, record: MemoryRecord) -> str: ...
    @abstractmethod
    def get(self, record_id: str) -> MemoryRecord | None: ...
    @abstractmethod
    def search(self, query: str, k: int = 10, memory_type: MemoryType | None = None) -> list[MemoryRecord]: ...
    @abstractmethod
    def delete(self, record_id: str) -> bool: ...
    @abstractmethod
    def count(self, memory_type: MemoryType | None = None) -> int: ...
```

### 4. Interacciones entre Memorias

| Origen → Destino | Método | Cuándo |
|------------------|--------|--------|
| Working → Episodic | `consolidate()` | Fin de interacción |
| Episodic → Semantic | `abstract()` | Al detectar patrón recurrente |
| Episodic → Long-Term | `index()` | Al almacenar (embedding generado) |
| Semantic → Long-Term | `index()` | Al almacenar (embedding generado) |
| Cualquiera → Olvido | `forget()` | Por TTL, decaimiento, o explícito |

## Consecuencias

### Positivas
- Contracto único `MemoryRecord` para todos los tipos de memoria
- Separación clara entre episodios y hechos
- Working Memory evita consultas innecesarias a KE
- Todos los componentes futuros (agentes, consenso) usan el mismo modelo

### Negativas
- Working Memory no persistente implica pérdida de contexto al reiniciar
- La abstracción Episodic → Semantic requiere un LLM (coste adicional)
- El embedding por cada registro añade latencia al almacenamiento

## Compatibilidad
- `MemoryRecord` es nuevo — no afecta a componentes existentes
- El KE existente (Long-Term Memory) no se modifica
- Los retrievers actuales conviven con MemoryStore
