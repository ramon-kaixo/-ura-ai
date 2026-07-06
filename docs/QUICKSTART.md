# URA Quickstart — 10 minutes to your first workflow

## Prerequisites

- Python 3.11+
- Docker (optional, for Qdrant)
- Git

## 1. Install

```bash
git clone https://github.com/ramon-kaixo/-ura-ai.git
cd ura-ai
pip install -e ".[dev]"
```

## 2. Start Qdrant (required for vector search)

```bash
docker run -d -p 6333:6333 qdrant/qdrant
```

Or using docker-compose:

```bash
docker compose up -d qdrant
```

## 3. Verify installation

```bash
python -c "from motor.intelligence.agents.runtime import MultiAgentRuntime; print('OK')"
```

## 4. Run a basic workflow

```python
from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.runtime import MultiAgentRuntime

runtime = MultiAgentRuntime()
runtime.register(ExecutorAgent())

result = runtime.execute_workflow("echo hello world", timeout=30)
print(f"Success: {result.success}")
print(f"Output: {result.output}")
```

## 5. Start the API server

```bash
python -m uvicorn motor.observability.http:app --reload
```

## 6. Check health

```bash
curl http://localhost:8000/health
curl http://localhost:8000/metrics
```

## 7. Commonly used commands

| Command | Description |
|---------|-------------|
| `pytest -q tests/` | Run all tests |
| `python -c "from motor.intelligence.agents.consensus import *"` | Verify consensus module |
| `curl localhost:8000/health` | System health |
| `curl localhost:8000/metrics` | Prometheus metrics |

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: motor` | Run from project root with `pip install -e .` |
| Qdrant connection refused | Start Qdrant: `docker run -d -p 6333:6333 qdrant/qdrant` |
| `pip install` fails (PEP 668) | Use `--break-system-packages` or create a venv |
