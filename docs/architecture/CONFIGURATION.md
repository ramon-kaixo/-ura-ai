# Configuration Reference

> **Fecha:** 2026-07-06
> **Alcance:** Cierre transversal F10–F13

---

## 1. Variables de Entorno

### 1.1 Configuración General

| Variable | Afecta | Valor por Defecto | Descripción |
|----------|--------|-------------------|-------------|
| `URA_CONFIG` | `UraConfig` | `""` | Ruta a archivo de configuración JSON |
| `URA_LOG_LEVEL` | `logging` | `"INFO"` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) |
| `URA_QDRANT_HOST` | `QdrantClient` | `"localhost"` | Host de Qdrant |
| `URA_QDRANT_PORT` | `QdrantClient` | `6333` | Puerto de Qdrant |
| `URA_TIMER_INTERVAL_MIN` | `PipelineOrchestrator` | `5` | Intervalo de pipeline automático (minutos) |
| `URA_SSH_USER` | `collector_asus.py` | `""` | Usuario SSH para colector remoto |
| `URA_API_KEY` | OpenClaw / API | `""` | API key para autenticación externa |
| `OPENROUTER_API_KEY` | Model Router | `""` | API key de OpenRouter |

### 1.2 Docker

| Variable | Afecta | Valor por Defecto | Descripción |
|----------|--------|-------------------|-------------|
| `URA_HOST` | `uvicorn` | `"0.0.0.0"` | Host de escucha del servidor HTTP |
| `URA_PORT` | `uvicorn` | `8000` | Puerto de escucha |
| `URA_OLLAMA_URL` | `QdrantClient` | `"http://localhost:11434"` | URL de Ollama |
| `URA_QDRANT_URL` | `QdrantClient` | `"http://localhost:6333"` | URL de Qdrant |
| `URA_DATA_DIR` | `UraConfig` | `"/data"` | Directorio de datos persistente |
| `URA_CONFIG_FILE` | `UraConfig` | `"/app/deploy/system_config.json"` | Config en Docker |
| `QDRANT_PORT` | docker-compose | `6333` | Puerto expuesto de Qdrant |
| `OLLAMA_PORT` | docker-compose | `11434` | Puerto expuesto de Ollama |

### 1.3 Legacy

| Variable | Afecta | Valor por Defecto | Descripción |
|----------|--------|-------------------|-------------|
| `OLLAMA_URL` | `core/qdrant_client.py` | `"http://localhost:11434"` | URL de Ollama (proxy legacy) |

---

## 2. UraConfig (Fuente de Verdad)

**Archivo:** `motor/core/config.py`
**Tipo:** Dataclass con 14 campos

```python
@dataclass
class UraConfig:
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    deploy_dir: str = "/home/ramon/URA/ura_ia_1972/deploy"
    data_dir: str = ""
    log_level: str = "INFO"
    is_vm: bool = True
    asus_host: str = "100.72.103.12"
    asus_port: int = 4198
    tailscale_iface: str = "tailscale0"
    timer_interval_min: int = 5
    failure_knowledge_path: str = ""
    baseline_path: str = ""
    auto_verify: bool = False
    schema_version: int = 301
```

Carga secuencial:
1. Valores por defecto
2. Archivo JSON (si `URA_CONFIG` está definido)
3. Override por variables de entorno (`URA_QDRANT_HOST`, `URA_QDRANT_PORT`, etc.)

---

## 3. Feature Flags (DegradedMode)

No hay feature flags booleanos explícitos. En su lugar, `DegradedMode` (motor/core/state.py)
proporciona control granular por subsistema:

| Subsistema | Flag real | Default | Cómo se degrada |
|------------|-----------|---------|-----------------|
| `"qdrant"` | `DegradedMode.is_degraded("qdrant")` | `False` | QdrantClient marca degraded tras N fallos |
| `"plugin:{name}"` | `DegradedMode.is_degraded(plugin_key)` | `False` | RegistryV2 marca degraded al fallar carga |
| `"hook:{key}"` | `DegradedMode.is_degraded(hook_key)` | `False` | HookManager tras N fallos con circuit breaker |

---

## 4. Configuración Docker

### 4.1 Dockerfile

| Elemento | Valor |
|----------|-------|
| Base image | `python:3.12-slim` (multi-stage) |
| User | `ura` (non-root) |
| Workdir | `/app` |
| Port | `8000` |
| Healthcheck | `CMD curl -f http://localhost:8000/health || exit 1` (30s, 5s timeout, 3 retries) |
| Entrypoint | `["/app/entrypoint.sh"]` |

### 4.2 docker-compose.yml (root)

| Service | Image | Ports | Volumes | Profiles | Depends On |
|---------|-------|-------|---------|----------|------------|
| `ura` | `ura:latest` | `${URA_PORT:-8000}:8000` | `ura_data:/data`, `ura_config:/app/deploy` | — | `qdrant` |
| `ura-worker` | `ura:latest` | — | same | `worker` | `qdrant` |
| `qdrant` | `qdrant/qdrant:latest` | `${QDRANT_PORT:-6333}:6333` | `qdrant_data:/qdrant/storage` | — | — |
| `ollama` | `ollama/ollama:latest` | `${OLLAMA_PORT:-11434}:11434` | `ollama_data:/root/.ollama` | `ollama` | — |

### 4.3 docker-compose.yml (deploy/ — unificado)

| Service | Profile | Ports | Memory Limit |
|---------|---------|-------|-------------|
| `open-webui` | core/all | `127.0.0.1:3080:8080` | 2G |
| `n8n` | core/all | `127.0.0.1:5678:5678` | 1G |
| `redis` | core/all | `127.0.0.1:6379:6379` | 512M |
| `mejora-continua` | sandbox/all | — | 2G (read-only) |
| `seguridad` | sandbox/all | — | 1G |
| `mantenimiento` | sandbox/all | — | 1G |
| `documentacion` | sandbox/all | `127.0.0.1:8087:8000` | 1G |
| `aprendizaje` | sandbox/all | — | 2G |
| `exploracion` | sandbox/all | — | 512M |
| `prometheus` | monitoring/all | `127.0.0.1:9090:9090` | — |

---

## 5. Configuración CLI

### 5.1 Argumentos Globales

| Flag | Descripción |
|------|-------------|
| `--config PATH` | Ruta a archivo de configuración |
| `--log-level LEVEL` | Nivel de logging (DEBUG, INFO, WARNING, ERROR) |

### 5.2 Subcomandos (29)

| Comando | Flags | Descripción |
|---------|-------|-------------|
| `pipeline` | `--dry-run` | Ejecutar pipeline completo |
| `scan` | — | Solo escanear |
| `diagnose` | — | Solo diagnosticar |
| `calibrate` | `--force` | Generar baseline |
| `status` / `dashboard` | — | Estado unificado |
| `cross` | — | Estado consolidado local+remoto |
| `trend` | — | Tendencia de salud |
| `graph` | — | Gráfico ASCII |
| `perf` | — | Rendimiento pipeline |
| `summarise` | — | Resumen MOTD |
| `history` | — | Historial incidentes |
| `check` | `--purge` | Preflight check |
| `verify` | — | Verificación post-cambio |
| `detect` | — | Detectar anomalías |
| `learn` | — | Analizar tendencias |
| `alerta` | — | Alertas journald |
| `health-check` | — | Health check completo |
| `qdrant-backup` | — | Backup Qdrant a JSON |
| `notify` | — | Notificaciones si alertas activas |
| `bench` | — | ⚠️ No implementado |
| `finalize` | `raw (checks -m)` | Pipeline test+commit+push |
| `test` | `raw` | Validar schema/config |
| `snapshot` | `raw` | Guardar estado repo |
| `maintenance` / `clean` | `raw (checks -d)` | Mantenimiento disco |
| `rotate` | `raw` | Rotar logs |
| `health` | `raw` | Salud GX10 |
| `alerts` / `logs` | `raw` | Sincronizar logs críticos |
| `snc` / `heartbeat` | `raw` | Estado SNC |
| `doctor` | `raw` | Diagnóstico completo |
| `metrics` | `raw` | Métricas router |
| `index` | `raw (checks -f)` | Indexar documentos RAG |
| `ask` | `raw (question)` | Consultar documentos |
| `memory` | `raw` | Estadísticas memoria RAG |

---

## 6. Rutas y Directorios

| Propósito | Ruta por Defecto | Configurable |
|-----------|------------------|--------------|
| Deploy (systemd, grafana, prometheus) | `{deploy_dir}/` | `UraConfig.deploy_dir` |
| Datos persistentes | `{data_dir}/` | `UraConfig.data_dir` |
| Baseline snapshots | `motor/data/snapshots/` | Fijo |
| Configuración JSON | `{deploy_dir}/system_config.json` | `URA_CONFIG_FILE` |
| Logs | stdout (JSON) | `URA_LOG_LEVEL` |
| Qdrant data (Docker) | `/qdrant/storage` | `QDRANT_PORT` |
| Ollama models (Docker) | `/root/.ollama` | `OLLAMA_PORT` |

---

## 7. Parámetros Configurables en Código

| Parámetro | Archivo | Default | Descripción |
|-----------|---------|---------|-------------|
| `EpisodeStoreConfig.max_episodes` | `motor/intelligence/memory/episodic.py` | `10000` | Máximo de episodios |
| `EpisodeStoreConfig.default_ttl` | `motor/intelligence/memory/episodic.py` | `604800` | TTL por defecto (7 días) |
| `Histogram.default_buckets` | `motor/observability/metrics.py` | `[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1, 5, 10]` | Buckets de latencia |
| `_MAX_EXPRESSION_LENGTH` | `knowledge/engine/rules.py` | `2048` | Máx caracteres en expresión de regla |
| `_MAX_AST_DEPTH` | `knowledge/engine/rules.py` | `10` | Máx profundidad AST |
| `_MAX_AST_NODES` | `knowledge/engine/rules.py` | `100` | Máx nodos AST |
| `_MAX_FUNCTION_CALLS` | `knowledge/engine/rules.py` | `10` | Máx llamadas por expresión |
| `_TIMEOUT_S` | `knowledge/engine/notify.py` | `10` | Timeout HTTP notificador |
| `_MAX_RETRIES` | `knowledge/engine/notify.py` | `3` | Reintentos máximos |
| `_BACKOFF_BASE_S` | `knowledge/engine/notify.py` | `1.0` | Backoff base (segundos) |
| `_BACKOFF_MAX_S` | `knowledge/engine/notify.py` | `10.0` | Backoff máximo |

---

## 8. Resumen: 36 Parámetros Configurables

| Categoría | Cantidad |
|-----------|----------|
| Variables de entorno | 12 |
| Campos UraConfig | 14 |
| DegradedMode subsystems | 3 |
| Docker Compose services | 10 |
| CLI subcomandos | 29 |
| CLI flags globales | 2 |
| Parámetros en código | 11 |
