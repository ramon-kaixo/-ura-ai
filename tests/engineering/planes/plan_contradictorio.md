# PLAN EJEMPLO 3 — Contradictorio (defecto: se contradice con ADR-007 y con el propio repo)

**Objetivo**: refactorizar `core/` para simplificar la carga de configuración.
**Por qué**: `core/config.py` y `motor/core/config.py` parecen duplicados.
**Contexto**: ADR-007 (Regla del Núcleo) establece que el núcleo NO se modifica sin ADR con justificación, plan de migración y rollback, y revisión obligatoria de segunda parte. Además `core/config.py` ya fue eliminado post-Fase 8 (la fuente de verdad es `motor/core/config.py`).
**Qué hacer**: fusionar ambas configs, eliminar `core/config.py` (o lo que exista), renombrar funciones públicas de `UraConfig`.
**Mínimo**: un único UraConfig con la API nueva.
**Comportamiento**: los consumidores usan la API renombrada.
**Validación**: tests existentes pasan.
**Cierre**: sin duplicados.
