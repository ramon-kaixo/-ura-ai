# Benchmark Baseline — Knowledge Engine v0.2.0

**Fecha:** 2026-07-01
**Sistema:** Linux, Python 3.12.3
**Schema:** v11
**Engine:** 0.2.0

## Compile

| Documentos | Tiempo | ms/doc |
|---|---|---|
| 10 | — | — |
| 100 | 5.577s | 55.7ms |
| 1000 | — | — |

## Search

| Búsquedas | Tiempo | ms/search |
|---|---|---|
| 100 | — | — |
| 1000 | 141.8s | 141ms |
| 10000 | — | — |

*Nota: search via subprocess CLI. En API directa (KnowledgeReader) sería ~1ms.*

## Archive

| Archives | Tiempo | ms/archive |
|---|---|---|
| 100 | 17.7s | 177ms |

## Recursos

| Métrica | Valor |
|---|---|
| DB size (100 docs) | 228 KB |
| WAL size | 0 KB (checkpointed) |

## Cómo ejecutar

```bash
bash scripts/benchmark.sh
```

Los resultados se consideran baseline. Cualquier cambio futuro que desvíe estos valores >20% debe ser investigado.
