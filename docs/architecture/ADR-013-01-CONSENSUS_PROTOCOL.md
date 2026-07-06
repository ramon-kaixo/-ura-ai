# ADR-013-01: Consensus Protocol — Votación Ponderada entre Agentes

> **Fecha:** 2026-07-05
> **Fase:** 13 (Producción)
> **Propósito:** Definir el protocolo de consenso entre agentes del Multi-Agent Runtime.
> **Estado:** ✅ Aprobado

## Contexto

Actualmente, el `SupervisorAgent` ejecuta subtasks secuencialmente sin
mecanismo de consenso. Si múltiples agentes producen resultados divergentes,
no hay forma de determinar cuál es correcto.

F12 demostró que el `MultiAgentRuntime` puede orquestar agentes, pero la
calidad de las decisiones depende de tener un mecanismo de votación cuando
los resultados difieren.

## Decisión

### 1. Arquitectura

```
MultiAgentRuntime
  └── ConsensusEngine (nuevo)
       ├── VotingStrategy (ABC)
       │   ├── MajorityVoting
       │   ├── WeightedVoting
       │   └── ConfidenceWeightedVoting
       └── ReflectionAgent (nuevo)
```

### 2. VotingStrategy

```python
class VotingStrategy(ABC):
    @abstractmethod
    def aggregate(
        self,
        results: list[AgentResult],
        weights: dict[str, float],
    ) -> AgentResult: ...
```

- `MajorityVoting`: el resultado con más votos gana
- `WeightedVoting`: cada agente tiene un peso configurable (por rol o por agente)
- `ConfidenceWeightedVoting`: el peso es dinámico según `AgentResult.confidence`

### 3. ConsensusEngine

```python
class ConsensusEngine:
    def __init__(self, strategy: VotingStrategy):
        ...

    def reach_consensus(
        self,
        task: AgentTask,
        agents: list[Agent],
        timeout: int = 30,
    ) -> AgentResult:
        # 1. Ejecutar agentes en paralelo (ThreadPoolExecutor)
        # 2. Recoger resultados
        # 3. Aplicar VotingStrategy.aggregate()
        # 4. Si hay empate → ReflectionAgent evalúa
        # 5. Retornar resultado con metadatos de votación
```

### 4. ReflectionAgent

Agente que evalúa la calidad de resultados existentes sin generar nuevo output:

```python
class ReflectionAgent(Agent):
    def run(self, task: AgentTask) -> AgentResult:
        candidates = task.input_data.get("candidates", [])
        # Evaluar cada candidato contra criterios de calidad
        # Devolver el mejor con puntuación de confianza
```

### 5. Votación por Defecto

| Configuración | Default |
|---------------|---------|
| Estrategia | `ConfidenceWeightedVoting` |
| Timeout por agente | 15s |
| Mínimo de agentes para consenso | 2 |
| Umbral de mayoría | > 50% |
| Peso por rol | Planner=1.0, Researcher=0.8, Executor=0.7, Validator=0.9, Supervisor=1.0 |

### 6. API de Integración

No se modifica la API de `Agent` ni `MultiAgentRuntime`. El `ConsensusEngine`
es un componente independiente que recibe agentes como parámetro.

## Compatibilidad
- No modifica `Agent` (ABC), `AgentResult`, `AgentTask`
- No modifica `MultiAgentRuntime`
- `ConsensusEngine` es nuevo y opcional
