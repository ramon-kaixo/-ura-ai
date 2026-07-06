# Plugin Development Guide

URA is extensible through Python classes implementing abstract base classes (ABCs).
This guide documents all public interfaces created in F11-F13.

## Agents

### Agent (ABC)

```python
from motor.intelligence.agents.base import Agent
from motor.intelligence.agents.message import AgentResult, AgentRole, AgentTask

class MyAgent(Agent):
    def __init__(self):
        self.id = "my_agent"
        self.name = "my_agent"
        self.role = AgentRole.EXECUTOR  # or RESEARCHER, VALIDATOR, etc.
        self.capabilities = ["my_capability"]
        self.status = AgentStatus.IDLE

    def run(self, task: AgentTask) -> AgentResult:
        # Your logic here
        return AgentResult(task_id=task.id, agent_id=self.id, success=True, output={})
```

### AgentTask

```python
@dataclass
class AgentTask:
    objective: str
    agent_role: AgentRole
    context: dict
    input_data: dict
    id: str
    priority: int
    timeout: int
```

### AgentResult

```python
@dataclass
class AgentResult:
    task_id: str
    agent_id: str
    success: bool
    output: dict
    error: str
    duration_ms: float
```

## Consensus

### VotingStrategy (ABC)

```python
from motor.intelligence.agents.consensus import (
    VotingStrategy, ConsensusResult, MajorityVoting, UnanimousVoting,
    WeightedConsensus, AgentWeightRegistry
)

class MyVotingStrategy(VotingStrategy):
    def name(self) -> str: ...
    def aggregate(self, results: list[AgentResult]) -> ConsensusResult: ...
```

## Reflection

### ReflectionStrategy (ABC)

```python
from motor.intelligence.agents.reflection import (
    ReflectionStrategy, ReflectionDecision, ReflectionAction
)

class MyReflectionStrategy(ReflectionStrategy):
    def reflect(self, result: AgentResult, iteration: int) -> ReflectionDecision: ...
```

## Parallel Execution

```python
from motor.intelligence.agents.parallel import ParallelExecutor, ExecutionResult

executor = ParallelExecutor(
    find_agent_fn=lambda aid: runtime.get_agent(aid),
    max_workers=4,
    fail_fast=False,
)
result = executor.execute(tasks)
```

## Memory System

### MemoryRecord — Unified contract

```python
from motor.intelligence.memory.record import MemoryRecord, MemoryType

record = MemoryRecord(
    type=MemoryType.EPISODIC,
    payload="content",
    importance=0.8,
    confidence=0.9,
    ttl=604800,  # 7 days
)
```

### MemoryStore (ABC)

```python
from motor.intelligence.memory.base import MemoryStore

class MyStore(MemoryStore):
    def store(self, record: MemoryRecord) -> str: ...
    def get(self, record_id: str) -> MemoryRecord | None: ...
    def search(self, query: str, k=10, memory_type=None) -> list[MemoryRecord]: ...
    def delete(self, record_id: str) -> bool: ...
    def count(self, memory_type=None) -> int: ...
```

### EpisodeStore — Concrete implementation

```python
from motor.intelligence.memory.episodic import EpisodeStore, EpisodeStoreConfig

store = EpisodeStore(config=EpisodeStoreConfig(persist_path="/data/episodes.db"))
```

### SemanticMemoryStore

```python
from motor.intelligence.memory.semantic import SemanticMemoryStore, SemanticFact

store = SemanticMemoryStore(persist_path="/data/facts.db")
store.store(SemanticFact(subject="server", predicate="has", object_value="64GB RAM"))
```

### FactExtractor (ABC)

```python
from motor.intelligence.memory.extractor import FactExtractor
from motor.intelligence.memory.semantic import SemanticFact

class MyExtractor(FactExtractor):
    def extract(self, episode: Episode) -> list[SemanticFact]: ...
```

## Retrieval

```python
from motor.intelligence.retrieval.vector import VectorRetriever
from motor.intelligence.retrieval.lexical import LexicalRetriever
from motor.intelligence.retrieval.hybrid import HybridRetriever
```

## Reranking

### BaseReranker (ABC)

```python
from motor.intelligence.reranking.base import BaseReranker

class MyReranker(BaseReranker):
    def rerank(self, query: str, candidates: list[dict]) -> list[dict]: ...
```

Built-in implementations:

| Class | Description | Status |
|-------|-------------|--------|
| `NoOpReranker` | Pass-through (default) | ✅ Production |
| `CrossEncoderReranker` | ms-marco-MiniLM via transformers | ⚠️ Experimental |
| `LLMReranker` | Ollama-based scoring | ⚠️ Experimental |

## Compression

### CompressionPolicy (ABC)

```python
from motor.intelligence.memory.compression import CompressionPolicy

class MyPolicy(CompressionPolicy):
    def should_run(self, store) -> bool: ...
    def select_candidates(self, store) -> list[Episode]: ...
```

## Forgetting

### ForgettingPolicy (ABC)

```python
from motor.intelligence.memory.forgetting import ForgettingPolicy, ForgettingContext

class MyPolicy(ForgettingPolicy):
    def name(self) -> str: ...
    def should_forget(self, record, context: ForgettingContext) -> tuple[bool, str]: ...
```

## Observability

```python
from motor.observability.logging import setup_logging, set_correlation_id
from motor.observability.metrics import MetricsRegistry, Counter, Gauge, Histogram, Timer
from motor.observability.exporter import format_prometheus
```

## Best Practices

1. **Implement ABCs, don't import implementations.** Depend on interfaces, not concrete classes.
2. **Use dependency injection.** Pass dependencies via `__init__` (e.g., `ExecutorAgent(executor=my_executor)`).
3. **Thread safety.** Use `threading.RLock` for shared state.
4. **Backward compatibility.** New parameters must have defaults. Don't remove or rename public methods.
5. **Test your plugin.** Run `pytest -q tests/` to ensure no regressions.
