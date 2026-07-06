# ADR-013-02: Deployment & Observability — Docker, pip, Prometheus, Documentación

> **Fecha:** 2026-07-05
> **Fase:** 13 (Producción)
> **Propósito:** Definir la estrategia de despliegue, empaquetado y observabilidad operativa para URA.
> **Estado:** ✅ Aprobado

## Contexto

URA funciona actualmente como un conjunto de scripts y servicios systemd en
una máquina específica (GX10). Para que sea instalable por terceros, se
necesita:

1. **Contenerización** (Docker) para eliminar dependencias del sistema anfitrión
2. **Empaquetado Python** (pip) para instalación estándar
3. **Observabilidad** (Prometheus + Grafana) para operación en producción
4. **Documentación** para usuarios externos

## Decisión

### 1. Docker

Se proporcionan dos imágenes:

| Imagen | Base | Contenido |
|--------|------|-----------|
| `ura-core` | `python:3.12-slim` | Motor URA + dependencias Python. Sin Ollama ni Qdrant |
| `ura-full` | `ura-core` + Ollama | Incluye Ollama para entornos todo-en-uno |

### 2. docker-compose.yml

```yaml
services:
  ura:
    build: .
    ports: ["8000:8000"]
    environment:
      - URA_OLLAMA_URL=http://ollama:11434
      - URA_QDRANT_URL=http://qdrant:6333
    depends_on: [ollama, qdrant]

  ollama:
    image: ollama/ollama
    volumes: [ollama_data:/root/.ollama]
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]

  qdrant:
    image: qdrant/qdrant
    volumes: [qdrant_data:/qdrant/storage]
```

### 3. pip install

```python
# pyproject.toml
[project]
name = "ura"
version = "0.13.0"
description = "URA — Multi-agent desktop assistant"

[project.scripts]
ura = "ura:main"

[project.optional-dependencies]
core = []        # Dependencias mínimas
all = []         # Dependencias completas (torch, transformers, etc.)
dev = []         # Dependencias de desarrollo (pytest, ruff, etc.)
```

### 4. Prometheus Exporter

El endpoint `/metrics` existente en `motor/observability/http.py` debe
exportar en formato OpenMetrics estándar (text/plain).

Métricas mínimas:

| Métrica | Tipo | Labels |
|---------|------|--------|
| `ura_workflows_total` | Counter | status |
| `ura_workflow_duration_seconds` | Histogram | — |
| `ura_agents_registered` | Gauge | — |
| `ura_memory_episodes_total` | Gauge | — |
| `ura_memory_facts_total` | Gauge | — |
| `ura_http_requests_total` | Counter | method, path, status |
| `ura_http_request_duration_seconds` | Histogram | method, path |

### 5. Documentación

| Documento | Formato | Contenido |
|-----------|---------|-----------|
| README.md | Markdown | Qué es URA, instalación rápida, ejemplos |
| QUICKSTART.md | Markdown | Tutorial de 5 minutos: instalar, configurar, usar |
| CLI_REFERENCE.md | Markdown | Todos los comandos con ejemplos |
| PLUGIN_DEV.md | Markdown | Plugin API, plugin.yaml, hooks |
| OpenAPI | JSON/YAML | Endpoints documentados automáticamente |

### 6. CI/CD

```yaml
# .github/workflows/ci.yml
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install .[dev]
      - run: ruff check .
      - run: pytest -q

  build:
    needs: [test]
    if: startsWith(github.ref, 'refs/tags/v')
    steps:
      - run: pip install build && python -m build
      - run: docker build -t ura .
      - run: docker push ghcr.io/ura/ura:${GITHUB_REF_NAME}
      - run: twine upload dist/*
```

## Compatibilidad
- No modifica endpoints existentes (`/metrics`, `/health`, `/ready`)
- `motor/observability/http.py` se extiende con exportador OpenMetrics
- La documentación es nueva, no modifica la existente
- `pyproject.toml` reemplaza `setup.py` o `requirements.txt` como fuente única
