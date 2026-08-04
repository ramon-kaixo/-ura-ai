# Sistema de Memoria de URA

**Fecha:** 2026-08-04
**Estado:** Verificado — 162 tests de memoria pasan (episódica, semántica, largo plazo, corto plazo)

## Arquitectura (4 capas + 1)

### 1. `scripts/pro/tuneladora/memory/` — Memoria del Pipeline
- **Responsabilidad:** Persistencia de ejecuciones del pipeline de validación
- **Submódulos:**
  - `episodic.py` — Episodios de cada ejecución ("hoy el pipeline pasó en 12s") — **95.2% cobertura**
  - `semantic.py` — Conceptos y relaciones aprendidas del código (`Concept`, `Relation`) — 100%
  - `long_term.py` — Archivado de resultados clave (`LTMEntry`) — 100%
  - `short_term.py` — Caché con TTL (snapshots de health checks) — 100%
- **Conectado a:** `runner._finish` → `episodic.record` + `ltm.store`; `phase_index` → `semantic.learn_concept`; `cache` → `ShortTermMemory`

### 2. `core/memoria/` — Memoria de Alto Nivel (dominio URA)
- **Responsabilidad:** Interfaz que usa el resto del sistema (bridge, consulta, compresor, vigilante)
- **Entrada:** Texto, eventos, resultados de búsqueda
- **Salida:** Contexto relevante para el agente
- **Nota:** Contiene `ficha.py` (dataclass `Idea` — captura de ideas, NO duplicado de episódica; ver ADR-220)

### 3. `motor/intelligence/memory/` — Stores Técnicos del Motor
- **Responsabilidad:** Implementación concreta de cada tipo de memoria del agente
- **Submódulos:** `episodic.py` (`Episode`/`EpisodeStore`), `semantic.py` (`SemanticFact`/`SemanticMemoryStore`), `hybrid.py`, `compression.py` (políticas de resumen), `forgetting.py`, `orchestrator.py`
- **Dependencias:** SQLite, Qdrant

### 4. `knowledge/engine/` — Motor de Conocimiento
- **Responsabilidad:** Indexación, búsqueda RAG, embeddings, FTS5
- **Entrada:** Documentos, web, conversaciones
- **Salida:** Fragmentos relevantes con score

### 5. `motor/observability/` — Trazas y métricas (tracing, métricas por proveedor LLM)

## Flujo de datos

```
Tuneladora -> runner._finish -> episodic.record -> SQLite (episódica del pipeline)
Tuneladora -> runner._finish -> ltm.store      -> SQLite (largo plazo)
Tuneladora -> phase_index     -> semantic.learn_concept -> SQLite (semántica)
Agente     -> core/memoria/bridge.py -> motor/intelligence/memory/episodic.py -> SQLite/Qdrant
Agente     -> core/memoria/consulta.py -> motor/intelligence/memory/semantic.py -> Qdrant
```

## NO son duplicados

Ver `docs/architecture/ADR-220-no-consolidar-duplicados.md`. Cada capa tiene
responsabilidad diferente (pipeline vs dominio vs motor vs conocimiento). La
duplicación de tecnología (Qdrant/SQLite) se resuelve en la capa de cliente,
no consolidando dominios.

## Verificación

```bash
# Tests de memoria (162 passed)
python3 -m pytest tests/integration/test_tuneladora_memory_*.py tests/unit/test_memoria_*.py -q

# La tuneladora guarda en las 4 memorias
grep -n "episodic.record\|ltm.store\|learn_concept\|ShortTermMemory" scripts/pro/tuneladora/pipeline/runner.py
```
