# Tarea B — Investigar puerto 5053 (ura-contraste)

**Fecha:** 2026-07-29
**Estado:** ✅ Completado

## Hallazgos

### ¿Qué escucha en 5053?
**No es ura-contraste.** Es `run_audit_api.py` — un microservicio FastAPI independiente en `/home/ramon/bin/run_audit_api.py`, lanzado manualmente (PID 2675, no es systemd).

### Endpoints disponibles
| Método | Path | Resultado |
|--------|------|-----------|
| GET | `/` | 404 |
| GET | `/health` | 404 |
| POST | `/run-audit` (sin key) | 401 |
| POST | `/run-audit` (con key) | 200 + ejecuta script |

### Único endpoint funcional: `POST /run-audit`
- Autenticación: `X-API-Key` header, key almacenada en `~/.ura/api_key_microservice.txt`
- Ejecuta: `bash /Users/ramonesnaola/bin/run_ura_audit.sh` — **ruta Mac que no existe en GX10**
- Timeout: 3600s

### ¿Por qué responde "Not Found" a `/v1/chat/completions`?
Porque la app solo define el endpoint `/run-audit`. No hay ruta `/v1/chat/completions` ni ningún proxy. FastAPI devuelve 404 por defecto para rutas no definidas.

### ¿Es ura-contraste?
No. `ura-contraste` (servicio systemd) está en **puerto 8002** según AGENTS.md. 5053 nunca fue ura-contraste.

### Recomendación
- Este microservicio no necesita `/v1/chat/completions` — comportamiento esperado.
- El script referencia una ruta Mac (`/Users/ramonesnaola/bin/run_ura_audit.sh`). Si el servicio se necesita funcional, habría que crear ese script en GX10 (out of scope).
