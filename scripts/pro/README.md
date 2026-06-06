# URA Pro — Módulo de Mantenimiento Avanzado

## Fases
1. `phase1_diagnosis.sh` — ruff + radon + pytest
2. `phase2_filter.sh` — ruff --fix + autoflake + ruff format
3. `phase3_architecture.sh` — radon + vulture + pytest
4. `phase4_rollback.sh` — Restaura snapshot si falla

## Uso
```bash
bash scripts/pro/tuneladora_pro.sh
```
