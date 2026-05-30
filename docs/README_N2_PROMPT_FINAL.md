# N2 Fase 1 — Prompt final (lo nuevo, sin duplicar)

Esta nota documenta lo entregado en respuesta al prompt "Fase 1 Infraestructura N2 (adaptada a realidad local)".

Decisión tomada por el usuario: **"solo lo nuevo"**. No se renombró nada, no se crearon alias. Solo se cubrieron los gaps reales sobre la base ya construida (F1+F2 N2 previas).

## Mapeo prompt → archivo

| Prompt pide | Archivo entregado | Reutiliza |
|---|---|---|
| `BaseSearchAgent` | `core/buscadores/base.py` | — |
| Refactor in-place de los 6 buscadores | Editados in-place añadiendo `class X(BaseSearchAgent)` + `search()` | Métodos legacy |
| `SearchOrchestrator` con dedup similitud | `core/buscadores/orchestrator.py` | — |
| `core/stealth_fetcher.py` con `fetch_page() → (text, final_url)` | `core/stealth_fetcher.py` | `random_user_agent` de `ura_stealth_browser.py` |
| `ura_n2_search.py` raíz con CLI + API | `ura_n2_search.py` | `SearchCache` + `SearchOrchestrator` |
| Cache SQLite anti-repetición | (ya existía) `core/ura_search_cache.py` | — |
| Validación de resultados | (ya existía) `core/ura_n2_validador.py` | — |

## Cambios in-place sobre legacy (sin destruir nada)

- `core/buscadores/buscador_noticias.py` — añadido `META` y `search(query, max_results)`
- `core/buscadores/buscador_estudios.py` — idem
- `core/buscadores/buscador_aplicaciones.py` — idem
- `core/buscadores/buscador_documentacion.py` — idem
- `core/buscadores/buscador_manuales.py` — idem (+ bugfix preexistente `Optional` ya aplicado en F2)
- `core/buscadores/buscador_tendencias.py` — idem

Todos los métodos `buscar_xxx()` originales siguen funcionando intactos. `search()` es solo una capa fina que delega y normaliza la salida.

## Cómo usar la Fase 1

### Programáticamente

```python
import asyncio
from ura_n2_search import n2_search

informe = asyncio.run(n2_search("agentes IA en local", use_cache=True, max_results=10))
print(informe["agents_used"])
print(informe["results"][:3])
```

### CLI

```bash
source .venv/bin/activate
python ura_n2_search.py "agentes IA en local" --max-results 5
python ura_n2_search.py "noticias hoy IA" --no-cache --json
python ura_n2_search.py "manual instalación ollama" --verbose
```

### Selección automática de agentes

El orquestador filtra por keywords antes de lanzar:

```
"noticias hoy IA"        → BuscadorNoticias
"manual instalación"      → BuscadorDocumentacion + BuscadorManuales
"random topic"           → todos los 6 (cobertura amplia)
```

## Tests añadidos

| Archivo | Tests |
|---|---|
| `tests/test_n2_orchestrator.py` | 9 (base + orchestrator + dedup similitud + ranking + errores) |
| `tests/test_n2_stealth_fetcher.py` | 5 (extracción texto, scripts/styles, fallback body, normalización) |
| `tests/test_ura_n2_search_entry.py` | 7 (n2_search API + cache hit/miss + CLI parser) |

**Total tests N2 acumulados: 76/76 ✅**
**Suite completa: 499/499 ✅**

## Lo que NO se hizo (por elección "solo lo nuevo")

- **No se crearon alias** `core/search_cache.py` ni `core/search_validator.py`. Si en el futuro quieres compatibilidad con esos nombres, son módulos triviales de añadir (5 líneas cada uno reexportando lo existente).
- **No se duplicó** la funcionalidad de `ura_search_cache.py` ni de `ura_n2_validador.py`. El prompt original asumía que no existían; en la realidad sí existen y funcionan (28 tests F1).
- **No se tocó** `core/buscadores_adapter.py` (de F2) ni el `ura_swarm_local.py` (más sofisticado, usa maletas). Coexisten con el nuevo orquestador ligero — son rutas paralelas: el orquestador para entrada simple, el swarm para flujos con maletas/router.

## Próximos pasos sugeridos

1. **Smoke test en vivo con DDG real:** `python ura_n2_search.py "tu_query" --max-results 5`
2. Cuando quieras Fase 3 (OpenClaw), instala el binario y conéctalo a `lanzar_n3_background()` (ya hay stub en `core/ura_nivel_router.py`).
3. Fase 4 (n8n exporter) cuando una maleta acumule 20+ usos reales.
