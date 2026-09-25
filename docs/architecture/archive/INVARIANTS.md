# Invariantes Arquitectónicos del Knowledge Engine

Estos invariantes son vinculantes. Cualquier cambio debe preservarlos.

## Capas y dependencias

```
connection.py    → única factory SQLite
lock.py          → flock, no lógica de negocio
jobs.py          → cola op_jobs, stale recovery
determinism.py   → hash + versionado
metrics.py       → Prometheus, pasiva
audit/           → trazabilidad, best-effort
compiler.py      → pipeline scanner→parser→validator→writer
reader.py        → solo consultas (nunca escribe SQLite)
archiver.py      → git bundle + restore
orchestrator.py  → coordina, NO contiene lógica de negocio
```

## Invariantes

### 1. Separación kg_* / op_*
- `kg_*` (grafo): se reescribe en cada compile. Nunca se modifica desde auditoría.
- `op_*` (operativo): persistente entre compilaciones. Auditoría, jobs, métricas.

### 2. Reader nunca escribe
- `reader.py` nunca ejecuta INSERT/UPDATE/DELETE en SQLite.
- Solo lectura (SELECT). Conexiones WAL mode.

### 3. Audit es best-effort
- `audit.write()` nunca lanza excepción. Falla silenciosamente con warning + métrica.
- Un fallo de auditoría nunca puede impedir una búsqueda ni un compile.
- Auditoría nunca escribe en `kg_*`.

### 4. Determinismo
- Dos compiles del mismo commit (mismos ficheros, mismo contenido) producen exactamente el mismo hash SHA-256.
- El hash excluye `updated_at`, `swapped_at`, `semantic`, `metadata`, `rowid`.
- `determinism_algorithm` versiona el método de cómputo ("sha256-v1").

### 5. Orchestrator coordina, no implementa
- `orchestrator.py` no contiene lógica de negocio.
- Toda lógica vive en: `compiler.py`, `jobs.py`, `lock.py`, `determinism.py`, `metrics.py`, `audit/`.

### 6. Connection factory única
- Ningún `sqlite3.connect()` fuera de `connection.py`.
- PRAGMAs obligatorios: WAL, foreign_keys=ON, synchronous=NORMAL, busy_timeout=5000.

### 7. Compile nunca conoce Archive
- `compiler.py` no importa `archiver.py` ni llama a funciones de archive.
- El archive se encola post-compile desde `orchestrator.py`.

### 8. Migraciones forward-only
- No existe downgrade. Schema version solo aumenta.
- `MINIMUM_SUPPORTED_SCHEMA` = 5, `MAXIMUM_SUPPORTED_SCHEMA` = 11.

### 9. WAL mode
- Todas las conexiones SQLite usan WAL journal mode.
- Lectores nunca bloquean escritores.
- Writers usan `BEGIN IMMEDIATE` para evitar deadlocks.

### 10. Dependencias unidireccionales
- Las capas solo dependen de capas inferiores, nunca al revés:
  ```
  CLI / API
      ↓
  Orchestrator
      ↓
  Compiler / Reader / Jobs / Rules
      ↓
  SQLite Writer / Audit / Archiver / Deduction
      ↓
  Connection / Lock / Migration
  ```
- Prohibido: que `connection.py` importe de `orchestrator.py`
- Prohibido: que `lock.py` importe de `jobs.py`

### 11. API pública congelada
```
knowledge.engine:
  - compile_source()     → pública
  - request_compile()    → pública
  - KnowledgeReader.search()  → pública
  - AuditBackend         → público (Protocol)
  - CompileResult        → público
  - AuditEvent           → público (frozen dataclass)
```
Todo lo demás es interno y puede cambiar sin previo aviso.
