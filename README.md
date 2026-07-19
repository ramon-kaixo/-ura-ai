# URA — Multi-Agent Platform

[![CI](https://github.com/ramon-kaixo/-ura-ai/actions/workflows/ci.yml/badge.svg)](https://github.com/ramon-kaixo/-ura-ai/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue)](https://python.org)
[![Ruff](https://img.shields.io/badge/code%20style-ruff-000000)](https://github.com/astral-sh/ruff)

URA is a modular multi-agent system with semantic retrieval, episodic/semantic memory,
a consensus-driven agent runtime, and full observability — designed for extensibility.

```
                                        ┌──────────────┐
                                        │   Ollama     │
                                        │  (LLM + emb) │
                                        └──────┬───────┘
                                               │
┌──────┐    ┌──────────┐    ┌──────────┐    ┌──┴────────┐    ┌──────────┐
│ User │───▶│ Runtime  │───▶│ Planner  │───▶│ Supervisor│───▶│ Agents   │
│ CLI  │    │          │    │          │    │           │    │ (exec,   │
│ API  │    │          │    │          │    │           │    │  research)│
└──────┘    └──────────┘    └──────────┘    └───────────┘    └──────────┘
                            ┌──────────┐    ┌──────────┐    ┌──────────┐
                            │ Memory   │    │ Retrieval│    │ Metrics  │
                            │ (episodic│    │ (hybrid) │    │ + Logging│
                            │  semantic│    │ + BM25   │    │ /health  │
                            └──────────┘    └──────────┘    └──────────┘
```

## Features

- **Multi-Agent Runtime**: Planner, Researcher, Executor, Validator, Supervisor, Reflection
- **Consensus Engine**: Majority, Unanimous, Weighted voting with configurable strategies
- **Memory System**: Episodic (sessions, TTL, SQLite), Semantic (facts, dedup, versioned)
- **Hybrid Retrieval**: Vector (Qdrant) + BM25 with weighted fusion and reranking
- **Observability**: Prometheus metrics, JSON logging, Grafana dashboard, health checks
- **Semantic Chunking**: Document splitting by structure (headings, paragraphs, overlap)
- **Docker**: Multi-stage image, docker-compose with Qdrant + optional Ollama
- **CI/CD**: GitHub Actions, PyPI package, wheel/sdist

## Installation

### Quick (pip)

```bash
pip install ura
ura --help
```

### From source

```bash
git clone https://github.com/ramon-kaixo/-ura-ai.git
cd ura-ai
pip install -e ".[dev]"
```

### Docker

```bash
docker compose up -d
# With Ollama:
docker compose --profile ollama up -d
```

## Quick Start

See [QUICKSTART.md](docs/QUICKSTART.md) for a complete 10-minute guide.

```bash
# Run a basic workflow
ura "search for EventBus documentation"

# Check system health
curl localhost:8000/health

# View metrics
curl localhost:8000/metrics
```

## Project Structure

```
ura-ai/
├── motor/
│   ├── core/
│   │   ├── fusion/         → F25 Knowledge Fusion (pipeline, FactIndex, FactHistory)
│   │   └── web/citation/   → CitationBundle, Evidence
│   ├── memory/             → F26 Historical Memory (Timeline, Journal, Snapshot, crypto)
│   ├── agents/             → F27 Autonomous Agents (CapabilityGate, ToolRunner, Scheduler, Orchestrator)
│   ├── platform/           → F28 Platform Protocols (Envelope, Tracing, Health, Metrics, RateLimiter)
│   ├── intelligence/
│   │   ├── agents/         → Legacy agent ABC, Runtime, Planner
│   │   ├── retrieval/      → Vector, BM25, Hybrid retrievers
│   │   ├── reranking/      → NoOp, LLM, CrossEncoder rerankers
│   │   ├── chunking.py     → SemanticChunker
│   │   └── memory/         → Episodic, Semantic, Compression, Forgetting
│   ├── events/             → EventBus, hooks, topics, compat
│   ├── pipeline/           → Dynamic pipeline executor
│   ├── plugin/             → Plugin system, manifests, registry
│   └── observability/      → Metrics, logging, health, exporter
├── deploy/
│   ├── grafana/            → Dashboard JSON
│   └── prometheus/         → Alerting rules
├── tests/                  → 1065+ tests
├── Dockerfile
├── docker-compose.yml
└── pyproject.toml
```

## Configuration

Configuration is via environment variables or `.env` file:

| Variable | Default | Description |
|----------|---------|-------------|
| `URA_OLLAMA_URL` | `http://localhost:11434` | Ollama endpoint |
| `URA_QDRANT_URL` | `http://localhost:6333` | Qdrant endpoint |
| `URA_LOG_LEVEL` | `INFO` | Log level |
| `URA_PORT` | `8000` | HTTP server port |
| `URA_HOST` | `0.0.0.0` | HTTP bind address |

## Running

```bash
# Development
python -m uvicorn motor.observability.http:app --reload

# Production
python entrypoint.sh

# Docker
docker compose up -d
```

## Testing

```bash
pip install -e ".[dev]"
pytest -q --tb=line tests/ motor/tests/
```

## Docker

```bash
docker build -t ura .
docker run -p 8000:8000 ura
```

## Observability

| Endpoint | Description |
|----------|-------------|
| `/health` | Health check (JSON) |
| `/ready` | Readiness check |
| `/metrics` | Prometheus OpenMetrics |

## Quickstart

```bash
pip install -e ".[dev]"
pytest tests/test_f28_b2_protocol.py -q  # 67 tests, ~6s
```

See [QUICKSTART.md](QUICKSTART.md) for detailed usage.

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history.

## Roadmap

| Phase | Focus | Status |
|-------|-------|--------|
| F10 | Stabilization | ✅ Closed |
| F11 | Platform (plugins, events, pipeline) | ✅ Closed |
| F12 | Intelligence (retrieval, memory, agents) | ✅ Closed |
| F13 | Production (Docker, CI/CD, docs) | ✅ Closed |
| F14 | Robustness (load, resiliency, profiling) | ✅ Closed |
| F25 | Knowledge Fusion | ✅ Closed |
| F26 | Historical Memory | ✅ Closed |
| F27 | Autonomous Agents | ✅ Closed |
| F28 | Platform Protocols | ✅ Closed |
| F29 | Production Readiness | ✅ Closed |

## Architecture

See [ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

## ADRs

All Architecture Decision Records are in [docs/architecture/](docs/architecture/).

## Contributing

See [PLUGIN_DEV.md](docs/PLUGIN_DEV.md) for the plugin API and extension points.

## License

MIT
