# URA N2 — Infraestructura de Búsqueda Local (Fases 1-2)

**Estado:** Fase 1 + Fase 2 completas y testeadas (55/55 tests N2 + 478 suite total).
**Fecha:** 2026-05-05.

## Qué es N2

`N2` es el nivel intermedio del sistema de búsqueda de URA:

| Nivel | Agente | Coste | Velocidad | Inteligencia |
|---|---|---|---|---|
| **N3** | OpenClaw local (futuro) | GPU/CPU | Lenta | Alta |
| **N2** | Swarm local de URA | CPU | Media | Media (maletas aprendidas) |
| **N1** | n8n (futuro) | cero | Rápida | Nula (workflows fijos) |

Esta entrega cubre solo **N2 sin OpenClaw**: URA puede desplegar agentes locales en paralelo, usar cache anti-repetición, validar URLs y detectar contradicciones.

## Módulos

Todos viven en `core/` y son async-first.

| Archivo | Responsabilidad |
|---|---|
| `core/ura_search_cache.py` | Cache SQLite async-safe con fingerprint SHA256 + TTL |
| `core/ura_maleta_manager.py` | CRUD de maletas JSON + validación + clonado emergency |
| `core/ura_ddg_client.py` | Cliente async de DuckDuckGo con jitter y retries |
| `core/ura_stealth_browser.py` | Wrapper async de Playwright con UA rotation + backoff 429/403 |
| `core/ura_n2_validador.py` | HEAD checks en paralelo + detección de contradicciones |
| `core/ura_swarm_local.py` | Orquestador del swarm (`asyncio.Semaphore` + `asyncio.Queue`) |
| `core/ura_nivel_router.py` | **(F2)** Router N1/N2/N3 + tracker de uso + decay temporal |
| `core/ura_n2_to_n8n_exporter.py` | **(F2 stub)** Exportador maleta → workflow n8n |
| `core/ura_searxng_client.py` | **(F2 opcional)** Cliente async para SearXNG local |
| `core/buscadores_adapter.py` | **(F2)** Adaptador async para los 6 buscadores legacy |

Configuración y datos:

| Ruta | Contenido |
|---|---|
| `config/maletas/` | Maletas versionadas en el repo (ejemplo: `fiscal_autonomos_es_v1.json`) |
| `~/.ura/maletas/` | Maletas generadas por URA (clones, aprendidas) |
| `~/.ura/search_cache.db` | SQLite de cache |
| `~/.ura/logs_n2/` | Logs de ejecución |

## Instalación

```bash
bash scripts/install_search_infra.sh            # instala todo
bash scripts/install_search_infra.sh --check    # verifica estado
bash scripts/install_search_infra.sh --uninstall
```

No requiere Docker. Fase 1 usa **DuckDuckGo directamente** en lugar de SearXNG. Si en Fase 2 quieres SearXNG local, se añadirá como opción.

## Uso básico

```python
import asyncio
from core.ura_maleta_manager import get_maleta_manager
from core.ura_swarm_local import get_swarm, default_agent_factory


async def buscar(tema: str, maleta_id: str) -> dict:
    mm = get_maleta_manager()
    maleta = mm.find_by_id(maleta_id)
    if maleta is None:
        raise ValueError(f"Maleta no encontrada: {maleta_id}")

    swarm = get_swarm()
    informe = await swarm.run(
        tema=tema,
        maleta=maleta.data,
        agent_factory=default_agent_factory,
    )
    return informe


if __name__ == "__main__":
    info = asyncio.run(buscar(
        "cuota autónomos 2025 España",
        "fiscal_autonomos_es_v1",
    ))
    print(info["resumen_ejecutivo"])
    print("Score:", info["score_calidad"])
    for fuente in info["fuentes_consolidadas"][:5]:
        print(f"  [{fuente['count']}] {fuente['url']}")
```

## Formato del informe (salida del swarm)

```python
{
  "exito": bool,
  "score_calidad": float,               # 0.0-1.0
  "resumen_ejecutivo": str,
  "resultados_por_agente": [            # AgentResult.to_dict()
    {
      "agente_id": str,
      "rol": str,
      "subtema_asignado": str,
      "estado": "ok" | "error" | "timeout",
      "resultados": [{titulo, url, resumen, fecha, fuente_tipo, confianza}],
      "herramientas_usadas": [str],
      "errores": [str],
      "tiempo_segundos": float
    }
  ],
  "contradicciones_detectadas": [{keyword, positivos, negativos, severidad}],
  "fuentes_consolidadas": [{url, titulo, cited_by, count}],
  "alertas": [str],
  "tiempo_total_segundos": float,
  "cache_usado": bool
}
```

## Límites y seguridad

- Máximo **10 agentes simultáneos globales** (`asyncio.Semaphore`)
- Máximo **3 swarms activos simultáneos** (`asyncio.Queue`)
- Timeout por agente: **120 s**; timeout por swarm: **300 s**
- **Nunca** `eval()`, `exec()`, `os.system()` con inputs dinámicos
- SQLite con `check_same_thread=False` + `asyncio.Lock` en escrituras
- Todas las rutas gestionadas con `pathlib.Path` (sin concatenación de strings)

## Qué NO incluye esta fase

- **N3 / OpenClaw** — se integra en Fase 3
- **Router de niveles** (`ura_nivel_router.py`) — Fase 2
- **Exportador a n8n** (`ura_n2_to_n8n_exporter.py`) — Fase 4
- **SearXNG** — opcional en Fase 2
- Refactor de `core/buscadores/*` a agentes del swarm — Fase 2

## Tests

```bash
source .venv/bin/activate
pytest tests/test_n2_search_cache.py tests/test_n2_maleta_manager.py \
       tests/test_n2_validador.py tests/test_n2_swarm.py -v
```

Resultado esperado: **28 passed**.
