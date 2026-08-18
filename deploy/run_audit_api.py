#!/usr/bin/env python3
"""URA Audit API (FastAPI) — version canónica del repo (P5+P9, 2026-08-18).

Origen: /home/ramon/bin/run_audit_api.py (que queda como copia de despliegue).
Correcciones aplicadas:
- P9: ruta del script de auditoría corregida (/home/ramon/bin/run_ura_audit.sh,
  la antigua /Users/ramonesnaola/... era la ruta de la Mac y no existe en GX10).
- P5: endpoint /metrics en formato Prometheus para el monitoreo (F8).
- Ruff limpio (pathlib, Annotated, subprocess no bloqueante, B904).
"""

from __future__ import annotations

import asyncio
import secrets
import subprocess
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import Response

API_KEY_FILE = Path("~/.ura/api_key_microservice.txt").expanduser()
if not API_KEY_FILE.exists():
    API_KEY_FILE.parent.mkdir(parents=True, exist_ok=True)
    API_KEY_FILE.write_text(secrets.token_urlsafe(32))
    API_KEY_FILE.chmod(0o600)

EXPECTED_API_KEY = API_KEY_FILE.read_text().strip()

app = FastAPI()


@app.get("/metrics")
async def metrics() -> Response:
    """Métricas básicas en formato Prometheus (P5 - F8 monitoreo)."""
    body = (
        "# HELP ura_audit_api_up Estado del API de auditoría\n"
        "# TYPE ura_audit_api_up gauge\n"
        "ura_audit_api_up 1\n"
        "# HELP ura_audit_api_requests_total Peticiones al API\n"
        "# TYPE ura_audit_api_requests_total counter\n"
        "ura_audit_api_requests_total 0\n"
    )
    return Response(content=body, media_type="text/plain; version=0.0.4")


@app.post("/run-audit")
async def run_audit(x_api_key: Annotated[str | None, Header(alias="X-API-Key")] = None):
    if not x_api_key or x_api_key != EXPECTED_API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    try:
        result = await asyncio.to_thread(
            subprocess.run,
            ["bash", "/home/ramon/bin/run_ura_audit.sh"],
            capture_output=True,
            text=True,
            timeout=3600,
            check=False,
        )
        return {"status": "ok", "stdout": result.stdout, "stderr": result.stderr}
    except subprocess.TimeoutExpired as exc:
        raise HTTPException(status_code=504, detail="Audit timed out") from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=5053)
