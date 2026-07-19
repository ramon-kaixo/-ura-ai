# Quickstart — URA Platform

## Prerrequisitos

- Python 3.11+
- pip

## Instalación

```bash
git clone https://github.com/ramon-kaixo/-ura-ai.git
cd ura_ia_1972

# Opción A: Core mínimo
pip install -e .

# Opción B: Con herramientas de desarrollo
pip install -e ".[dev]"

# Opción C: Con GPU (NVIDIA)
pip install -e ".[gpu]"
```

## Verificar instalación

```bash
python3 -c "from motor.core.config import UraConfig; print('OK')"
```

## Ejecutar tests

```bash
# Tests de protocolo (rápidos, ~6s)
pytest tests/test_f28_b2_protocol.py -q

# Tests de plataforma
pytest tests/test_platform_delivery.py tests/test_platform_resilience.py -q

# Tests de memoria
pytest tests/test_f26_b2_memory.py -q
```

## Uso básico

### Memoria histórica

```python
from motor.memory import Memory

m = Memory()
m.append({"type": "note", "data": "Hello URA"})
result = m.state_at()
print(result)
```

### Circuit Breaker

```python
from motor.platform.resilience import CircuitBreaker

cb = CircuitBreaker("api", failure_threshold=3, recovery_timeout=30)
result = cb.call(my_api_function)
if result is None:
    print("Circuit is OPEN — usando fallback")
```

### Agente básico

```python
from motor.agents.models import AgentTask, AgentRole
from motor.agents.scheduler import AgentScheduler

scheduler = AgentScheduler()
result = scheduler.submit(
    AgentTask(objective="saludar", agent_role=AgentRole.PLANNER)
)
print(result)
```

## Arquitectura

Ver [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) para documentación completa.

## Roadmap

Ver [AGENTS.md](AGENTS.md) para el roadmap de fases completado.

## Scripts útiles

```bash
# Pipeline de mejora continua
python3 scripts/pro/tuneladora_master.py --dry-run

# Benchmarks de rendimiento
python3 scripts/pro/benchmark_f29_b2.py --output resultados.json

# Backup de memoria
python3 scripts/pro/backup_f26_memory.py backup
```
