# Tarea B — Investigar puerto 5053

**Fecha:** 2026-07-29
**Estado:** ✅ Completado

## Hallazgos

### Puertos

| Puerto | Proceso | PID | Servicio systemd |
|--------|---------|-----|------------------|
| **5053** | `python3` → `run_audit_api.py` | 2675 | No (proceso manual) |
| **8002** | `uvicorn` → `proxy_contraste` | 3598 | `ura-contraste.service` ✅ |

### Port 5053 — `run_audit_api.py`

Ubicación: `/home/ramon/bin/run_audit_api.py`
Tipo: FastAPI microservicio manual
Único endpoint: `POST /run-audit` (requiere `X-API-Key`)
Ejecuta: `bash /Users/ramonesnaola/bin/run_ura_audit.sh` — **ruta Mac inexistente en GX10**

```
GET  /                        → 404
GET  /health                  → 404
POST /v1/chat/completions     → 404
POST /run-audit (sin key)     → 401
POST /run-audit (con key)     → 200 + error bash (ruta Mac)
```

### Port 8002 — ura-contraste (real)

```
GET /                        → 404
GET /health                  → 200 {"status":"healthy",...}
```

### Conclusión

5053 **nunca fue ura-contraste**. Es un microservicio de auditoría independiente que no tiene endpoint `/v1/chat/completions`. El 404 es comportamiento esperado.
