#!/usr/bin/env python3
"""Webhook receptor de Alertmanager -> notificaciones Telegram/Pushover (F8).

Recibe los POST de Alertmanager (formato v4) en /webhook/ura-alerts y envia la
notificacion via motor.core.notifier.notify() (Telegram + Pushover si hay
secretos configurados; si no, degrada con log y responde 200 igualmente).

Uso (docker compose): servicio webhook-alerts, puerto host 9105.
Sin secretos configurados el servicio sigue operativo (solo loguea).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

sys.path.insert(0, str(Path("~/URA/ura_ia_1972").expanduser()))

try:
    from motor.core.notifier import notify
except ImportError:
    notify = None  # degradacion: contenedor sin motor/ montado

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("ura-alerts-webhook")

app = FastAPI(title="ura-alerts-webhook")

_LEVEL_BY_SEVERITY = {"critical": "critical", "warning": "warning", "info": "info"}


@app.get("/health")
async def health() -> Response:
    """Health check para monitoreo."""
    return Response("ok")


@app.post("/webhook/ura-alerts")
async def webhook(request: Request) -> JSONResponse:
    """Receptor de webhooks de Alertmanager (status firing/resolved)."""
    try:
        payload = await request.json()
    except Exception as exc:
        log.warning("JSON invalido: %s", exc)
        return JSONResponse({"error": "bad json"}, status_code=400)

    alerts = payload.get("alerts", [])
    received = 0
    notified = 0
    for alert in alerts:
        received += 1
        status = alert.get("status", "firing")
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        severity = labels.get("severity", "warning")
        alertname = labels.get("alertname", "alerta URA")
        summary = annotations.get("summary", alertname)
        job = labels.get("job", "?")
        instance = labels.get("instance", "?")

        if status == "resolved":
            msg = f"RECUPERADA: {summary} (job={job}, instance={instance})"
            level = "info"
        elif severity == "critical":
            msg = f"CRITICA: {summary} (job={job}, instance={instance})"
            level = "critical"
        else:
            msg = f"ALERTA: {summary} (job={job}, instance={instance})"
            level = "warning"

        if notify is None:
            log.warning("notifier no disponible (motor/ no montado): %s", msg)
            ok = False
        else:
            try:
                ok = notify(msg, level=level)
            except Exception as exc:
                log.warning("notify fallo para %s: %s", alertname, exc)
                ok = False
        if ok:
            notified += 1
        else:
            log.info("notify no enviada (sin secretos?): %s", msg)

    log.info("webhook: %d alertas recibidas, %d notificadas", received, notified)
    return JSONResponse({"received": received, "notified": notified})


if __name__ == "__main__":
    import uvicorn

    # 0.0.0.0 dentro del contenedor docker (red interna) — S104: caso de uso legitimo
    uvicorn.run(app, host="0.0.0.0", port=9105)  # noqa: S104
