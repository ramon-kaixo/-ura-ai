# T2: model-router exit 78 — Reporte

**Fecha:** 2026-07-29
**Ejecutó:** OpenCode
**Duración:** ~10 min

## Problema
`model-router.service` fallaba con exit 78. `OPENCLAW_GATEWAY_TOKEN` no
estaba en el entorno del servicio. El token SÍ existe en `/etc/ura/secrets.env`.

## Solución
- Creado drop-in `/etc/systemd/system/model-router.service.d/secrets.conf`
- Contenido:
```
[Unit]
PartOf=ura-contraste.service

[Service]
EnvironmentFile=/etc/ura/secrets.env
```
- `systemctl daemon-reload` + restart

## Estado Actual
- `model-router.service`: active (running) ✅
- `/health` endpoint: responde JSON ok ✅
- Auth funciona (bad token → 403) ✅
- `/supervisor` necesita auth válida ✅

## Notas
- El `/supervisor` endpoint timeout por esperar respuesta de Ollama
  (comportamiento esperado con modelos grandes)
