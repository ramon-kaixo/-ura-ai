# Tarea B — Investigar ura-contraste (puerto 5053 vs 8002)

**Fecha:** 2026-07-29
**Estado:** ✅ Completado

## Hallazgos

### Puerto 5053 — `run_audit_api.py`
- **Proceso**: `python3` PID 2675, `/home/ramon/bin/run_audit_api.py`
- **Tipo**: FastAPI microservicio manual (no systemd)
- **Único endpoint**: `POST /run-audit` (autenticado con `X-API-Key`)
- **Roto**: Ejecuta `bash /Users/ramonesnaola/bin/run_ura_audit.sh` — ruta Mac inexistente
- **NO es ura-contraste**

### Puerto 8002 — ura-contraste (real)
- **Servicio**: `ura-contraste.service` ✅ active (running)
- **Proceso**: `uvicorn` PID 3598
- **Endpoint `/health`**: ✅ responde 200
- **Endpoint `/metrics`**: ✅ scrapeado por Prometheus Docker (172.17.0.4)
- **Endpoint `/v1/chat/completions`**: 404 (comportamiento esperado — no es su función)

## Conclusión
ura-contraste funciona correctamente en puerto 8002. El 404 en `/v1/chat/completions` es esperado. Puerto 5053 es un microservicio independiente de auditoría.
