# ADR-220 — Consolidación de duplicados: decisión de NO consolidar

**Estado:** PROPUESTO (pendiente de aprobación de Ramón)
**Fecha:** 2026-08-04
**Fase:** Plan Maestro v3.2 — Fase 2 (Limpieza), tarea 2.3
**Contexto:** El Plan Maestro v3.2 marcó 5 pares de módulos como "duplicados"
candidatos a consolidación (escaneo, memoria episódica, memoria semántica,
compresión, pipeline). Este ADR documenta el análisis real de cada par y la
decisión resultante.

## Análisis real de los 5 pares

| # | Par | Evidencia | ¿Duplicado real? |
|---|-----|-----------|------------------|
| 1 | `motor/scanner/scanner.py` (391 líneas) vs `knowledge/engine/scanner.py` (192) | Ambos escanean directorios, pero contratos distintos: `Scanner` (clase, usada por `motor/pipeline/orchestrator` y `cmd_pipeline`) vs `scan_source`/`scan_incremental`/`take_snapshot` (funciones exportadas por `knowledge/engine/__init__`) | **No** — paralelos por frontera de subsistema |
| 2 | `core/memoria/ficha.py` (50) vs `motor/intelligence/memory/episodic.py` (398) | `ficha.py` define el dataclass `Idea` (captura de ideas); `episodic.py` define `Episode`/`EpisodeStore` (acciones del agente). Importadores disjuntos | **No** — conceptos distintos, mismo nombre genérico |
| 3 | `core/memoria/qdrant_store.py` (212) vs `motor/intelligence/memory/semantic.py` (276) | Ambos usan Qdrant pero con modelos distintos: `MemoryPipelineStore` + `_make_id(Idea)` vs `SemanticFact`/`SemanticMemoryStore`/`consolidate_episodes` | **No** — comparten tecnología, no contrato |
| 4 | `core/memoria/compresor.py` (120) vs `motor/intelligence/memory/compression.py` (285) | `compresor.py`: texto → LLM → ideas estructuradas (`comprimir_a_ideas`, usado por `vigilante.py`/`consulta.py`); `compression.py`: `CompressionPolicy`/`SummaryRecord` (resumen de episodios) | **No** — mismo nombre, funciones opuestas |
| 5 | `motor/pipeline/orchestrator.py` (135) vs `scripts/pro/tuneladora_mantenimiento.py` (537) | `Orchestrator` (clase del motor) vs tuneladora (servicio operativo con systemd timer, 6 fases de mantenimiento) | **No** — orquestación de módulos vs mantenimiento del sistema |

## Decisión

**NO consolidar ninguno de los 5 pares.** Los "duplicados" del plan se detectaron
por coincidencia de nombre, no por duplicación funcional. Cada par opera en una
frontera de subsistema distinta (core/memoria = captura de ideas; motor/intelligence/memory
= memoria del agente; motor/scanner vs knowledge/engine = frontera motor/knowledge).

**Justificación (ADR-007):**
1. La consolidación exigiría cambiar contratos en núcleos semánticamente congelados
   (`knowledge/engine` exporta `scan_source` en su `__init__`; `core/memoria` alimenta
   `vigilante.py`/`consulta.py`) — prohibido sin migración completa y reversible.
2. Beneficio estimado: ~1,000 líneas menos. Riesgo: romper 2 subsistemas en producción
   con el agente paralelo modificando `knowledge/engine/` activamente.
3. La duplicación real de tecnología (Qdrant) se resuelve en la capa de cliente
   (`motor/core/qdrant_client.py`, ya 100% cubierto), no consolidando dominios.

## Alternativa adoptada

1. **Documentar el análisis** en `docs/audit/DUPLICADOS.md` (este ADR) para re-evaluar
   cuando el subsistema se estabilice.
2. **Criterio de consolidación futuro** (para nuevos candidatos):
   - Mismo contrato público (mismas firmas y semántica observable)
   - Mismos consumidores o consumidores en la misma zona
   - Ambos en el mismo subsistema (no cruzar fronteras motor/core/knowledge)
3. **Deprecación en vez de fusión**: si algún día `motor/intelligence/memory` absorbe
   `core/memoria`, hacerlo por política de deprecación (v3.x marcar DeprecationWarning,
   v4.0 eliminar), no por consolidación en caliente.

## Impacto
- Ningún cambio de código.
- Se cierra la tarea 2.3 del plan con decisión documentada en lugar de ejecución.

## Aprobación
- [ ] Ramón aprueba NO consolidar
- [ ] Ramón prefiere consolidar algún par (indicar cuál)
