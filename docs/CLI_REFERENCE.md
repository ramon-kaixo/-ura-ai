# URA CLI Reference

> **Note**: URA is primarily a Python library/API. The CLI is available via the `ura` entry point.

## `ura` — Entry point

Installed by `pip install ura` or `pip install -e .`.

### Syntax

```bash
ura [command] [options]
```

### Commands

| Command | Description | Arguments |
|---------|-------------|-----------|
| `help` | Show help | — |
| `status` | System status | — |
| `doctor` | System diagnostics | — |
| `health` | Health check | — |
| `pipeline` | Run pipeline | `--dry-run` |

### Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 78 | Configuration error |

## Python API (primary interface)

### Multi-Agent Runtime

```python
from motor.intelligence.agents.executor import ExecutorAgent
from motor.intelligence.agents.runtime import MultiAgentRuntime

runtime = MultiAgentRuntime()
runtime.register(ExecutorAgent())
result = runtime.execute_workflow("search for documentation", timeout=30)
```

### Consensus

```python
from motor.intelligence.agents.consensus import (
    VotingEngine, MajorityVoting, WeightedConsensus, AgentWeightRegistry
)

engine = VotingEngine()
engine.strategy = WeightedConsensus(registry)
result = engine.vote(results)
```

### Memory

```python
from motor.intelligence.memory.episodic import Episode, EpisodeStore

store = EpisodeStore()
store.store(Episode(payload="interaction", session_id="session_1"))
episodes = store.get_by_session("session_1")
```

### Retrieval

```python
from motor.intelligence.retrieval.hybrid import HybridRetriever
from motor.intelligence.retrieval.vector import VectorRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever

hybrid = HybridRetriever(VectorRetriever(qc), LexicalRetriever(), alpha=0.7, beta=0.3)
results = hybrid.search("query", k=10)
```

### Observability

```python
from motor.observability.logging import setup_logging, set_correlation_id

setup_logging(level="INFO", json_output=True)
set_correlation_id()
```

### API Server

```bash
python -m uvicorn motor.observability.http:app --host 0.0.0.0 --port 8000
```

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/metrics` | GET | Prometheus metrics |

## Docker

```bash
docker compose up -d                    # URA + Qdrant
docker compose --profile ollama up -d   # + Ollama
docker compose logs -f                  # Follow logs
```
