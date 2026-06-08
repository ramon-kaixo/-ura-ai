# Arquitectura URA

## Model Router
El router clasifica peticiones y selecciona el mejor modelo.
Usa Ollama en puerto 11434 y expone en 11435.
Tiene cache de prompts con TTL de 7200s.

## Mantenimiento
El sistema de mantenimiento limpia Docker, logs y caches.
Ejecuta vía cron diario a las 3am.
Tiene modo dry-run para previsualizar cambios.

## SNC
El Sistema Nervioso Central monitorea procesos cada 10s.
Si un proceso falla, ejecuta el emergency_runbook.json.
Tras 3 intentos fallidos, activa OpenClaw.
