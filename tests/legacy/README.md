# Legacy Tests

Standalone test scripts with custom runners (`check()` pattern, `if __name__ == "__main__"`).
Not discoverable by pytest. Candidatos a convertir a pytest en el futuro.

| File | Lines | Descripción |
|------|-------|-------------|
| `test_sda.py` | 448 | SDA (Sistema de Debate entre Agentes): DebateLock, debate_engine, plan_validator |
| `test_unit.py` | 552 | Suite unitaria URA v3.0: config_manager, model_router, mantenimiento, monitor, memory_engine |
