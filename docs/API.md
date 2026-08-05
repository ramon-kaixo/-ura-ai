# API de URA — Endpoints documentados

**Fecha:** 2026-08-05
**Fuente:** grep verificado sobre el código (core/mochila/mochila_server.py, motor/assistant/api/routes.py, knowledge/engine/api.py)

## Servicios y puertos

| Servicio | Puerto | Base |
|---|---|---|
| ura-api | 8000 | API principal |
| ura-audit-api | 8080 | Auditoría |
| ura-contraste | 8002 | Proxy contraste + telemetría |
| ura-mochila | — | Mochila (breaker, memoria) |
| model-router | 11435 | LLM router |
| Ollama | 11434 | LLM local |

## Endpoints verificados (grep sobre código)

### Health y métricas
- `GET /health` — health check
- `GET /metrics` — métricas Prometheus
- `GET /status` — estado del servicio
- `GET /memoria/health` — salud de memoria

### Mochila (core/mochila/mochila_server.py)
- `GET /breaker` — estado de circuit breakers
- `POST /breaker/reset/{provider}` — reset de breaker
- `GET /memoria/vigilancia/parte` — partes de vigilancia
- `POST /admin/acquire_boot_vram` — adquisición VRAM (admin)

### Knowledge Engine (knowledge/engine/api.py)
- `GET /documents/{doc_id}` — documento
- `GET /feedback/top` — feedback top
- `GET /memory` / `GET /memory/{memory_id}` — memoria
- `GET /metadata/lineage/{asset_id}` — linaje
- `GET /rules` — reglas
- `POST /archive` — archivar
- `POST /compile` / `POST /compile/sync` — compilar

### Motor (motor/assistant/api/routes.py)
- `GET /v1/models` — modelos LLM disponibles
- `GET /metrics/cost` — coste
- `GET /metrics/rate/{provider}` — rate por proveedor

## Regla para load testing

Solo estos endpoints documentados entran en locustfile.py (B-22).
Si un endpoint no está aquí, no se incluye sin preguntar a Ramón.
