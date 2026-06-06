# URA AI Cluster: Arquitectura de Inferencia de Alta Disponibilidad

**Estado:** Producción (Hardened)  
**Latencia Promedio:** <1.5ms  
**Nodos:** 2 (Cliente Ligero + Servidor Computacional)  

## Topología
```mermaid
graph TD
    subgraph "Cliente Mac M4" --> NET{Origen de IP?}
    NET -- "Local" --> ROUTER[Model Router]
    NET -- "Remoto" --> TS[Tailscale] --> ROUTER
    ROUTER -- "TURBO" --> ASUS[ASUS GX10 - Ollama]
    ROUTER -- "ECO" --> LOCAL[Mac M4 local]
    subgraph "ura-supervisor (19 corrutinas)"
        EB[ZeroMQ Event Bus]
        ING[modules/ingest/] --> EB
        AI[modules/ai/model_broker] --> EB
        INF[modules/infra/action_handler]
    end
```

## 19 Corrutinas
Watchdogs: redis, disk, network, heartbeat  
Collectors: metrics, system  
Validators: config, syntax, imports  
Optimizers: cache  
Orquestador: orchestrator, telemetry, ura_alert  
Ingesta: data_scraper, data_analyzer, ingest_coordinator  
AI/Infra: ai_broker, ipc_server, heartbeat_task  

## Comandos
- `ura-sup TURBO|ECO|AUTO` — cambiar modo
- `ura-sup health|tasks` — estado supervisor
- `python3 scripts/validate_baseline.py` — validar baseline
