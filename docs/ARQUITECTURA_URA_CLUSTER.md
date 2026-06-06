# URA AI Cluster: Arquitectura de Inferencia de Alta Disponibilidad

**Estado:** Producción (Hardened)  
**Latencia Promedio:** <1.5ms  
**Nodos:** 2 (Cliente Ligero + Servidor Computacional)  
**Última actualización:** 2026-06-06

## 1. Topología del Sistema

```mermaid
graph TD
    subgraph "Capa de Cliente (Mac M4)"
        M4[Mac M4 - Nodo Central]
        CLI[Terminal / IDE] --> M4
    end
    subgraph "Capa de Red (Consciencia de Ubicación)"
        NET{¿Origen de IP?}
        M4 --> NET
        NET -- "Local (192.168.x.x)" --> LAN[Red Local / Ethernet]
        NET -- "Remoto (100.x.x.x)" --> TS[Túnel Tailscale]
    end
    subgraph "Capa de Enrutamiento (URA Model Router)"
        ROUTER{Decision Engine}
        LAN --> ROUTER; TS --> ROUTER
        ROUTER -- "Modo TURBO" --> RL[Rate Limiter: 100 req/min]
        ROUTER -- "Modo ECO" --> LOCAL[Inferencia Local Mac M4]
        RL --> CACHE[(Cache In-Memory TTL: 4h)]
    end
    subgraph "Capa de Computación (ASUS GX10)"
        CACHE --> PRE[ExecStartPre: Limpieza Puerto 11435]
        PRE --> SYS[Systemd: model-router.service]
        SYS --> OLLAMA[Ollama Core]
        OLLAMA --> M1((Llama 3.3 70B))
        OLLAMA --> M2((Qwen 2.5 32B))
        OLLAMA --> M3((DeepSeek Coder))
    end
    subgraph "Capa de Supervisor (ura-supervisor)"
        SUP[19 corrutinas] --> EB[ZeroMQ Event Bus]
        EB --> ING[modules/ingest/]
        EB --> AI[modules/ai/model_broker.py]
        AI --> INF[modules/infra/action_handler.py]
    end
```

## 2. Mecanismos de Resiliencia

- **ExecStartPre:** `fuser -k 11435/tcp` elimina zombies antes de arrancar
- **Restart=always** + **RestartSec=5**: auto-recuperación en <5s
- **Health check:** cada 5min vía systemd timer
- **Chaos maintenance:** cada domingo 03:00 (SIGKILL + auto-recovery)
- **StateManager:** Redis → SQLite → JSON fallback en cadena

## 3. 19 Corrutinas del Supervisor

| Categoría | Corrutinas |
|---|---|
| Watchdogs | watchdog_redis, watchdog_disk, watchdog_network, watchdog_heartbeat |
| Collectors | collector_metrics, collector_system |
| Validators | validator_config, validator_syntax, validator_imports |
| Optimizers | optimizer_cache |
| Orquestador | orchestrator, telemetry, ura_alert |
| Ingesta | data_scraper, data_analyzer, ingest_coordinator |
| AI/Infra | ai_broker, ipc_server, heartbeat_task |

## 4. Comandos de Operación

```bash
ura-sup TURBO | ECO | AUTO   # Cambiar modo
ura-sup health | tasks       # Estado del supervisor
ura-status                    # Dashboard completo
ura-status --quick            # Resumen una línea
ura-query --stats             # Estadísticas de telemetría
mode turbo | eco | auto       # Cambio rápido de modo
```
