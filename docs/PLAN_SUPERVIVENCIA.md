# URA — Plan de Supervivencia

## Escenario A: Cae el Mac
- **Sintomas**: Timers launchd detenidos, Dashboard :5101 no accesible.
- **Diagnostico**: `curl http://127.0.0.1:5103/health` falla.
- **Accion**: GX10 sigue operando Enjambre, Frigate, centinela.
- **Recuperacion**: Restaurar timers launchd.

## Escenario B: Cae el GX10
- **Sintomas**: Ollama, Frigate, Enjambre no responden.
- **Diagnostico**: `curl http://100.127.206.86:11434/api/tags` falla.
- **Accion**: Mac ejecuta Tuneladora local. Watchdog notifica.
- **Recuperacion**: `bash scripts/bootstrap_gx10.sh`

## Escenario C: Cae la red (Tailscale)
- **Sintomas**: Mac y GX10 no se ven.
- **Diagnostico**: `ping 100.127.206.86` falla.
- **Accion**: Cada maquina opera autonomamente.
- **Recuperacion**: Tailscale se reconecta automaticamente.
