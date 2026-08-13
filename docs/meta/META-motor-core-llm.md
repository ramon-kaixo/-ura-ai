# META: motor/core/llm/ (profiler y utilidades LLM)

## Idea de desarrollo
Utilidades del runtime LLM del motor: profiling de memoria y observabilidad
sin bloquear el hot path.

## Archivos
| Archivo | Qué hace | Errores conocidos (arreglo, fuente) | Idea original |
|---------|----------|--------------------------------------|---------------|
| motor/core/llm/profiler.py | Profiling de memoria/CPU del LLM | DEADLOCK en Python 3.13: gc.collect() en hot path eliminado (TASK-20260813-002, commit fa910fdd) y take_snapshot(stop-the-world) → get_traced_memory no bloqueante (TASK-20260813-006, commits 8e2e6196, 7ed1c021, 23c18748) | Medir recursos sin parar el mundo |
| tests/unit/test_motor_llm_observability.py | Tests de observabilidad del LLM | test_monitor_thread_safe 3,7s tras fix (TASK-20260813-006) | Cobertura del profiler |

## Historia de la zona
- 2026-08-13: deadlock 3.13 resuelto en 2 pasos (TASK-002: gc.collect fuera del hot path; TASK-006: snapshot no bloqueante). CI verde 3 runs.
- 2026-08-13: 84 tests de observabilidad pasan (TASK-006).