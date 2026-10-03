<!-- Engineering Process v1.0 — PLAN CONTRADICTORIO (ejemplo para prueba conductual B2) -->

# PLAN EJEMPLO — Migración a base de datos PostgreSQL

## 1. ¿QUÉ QUIERO CONSEGUIR?
Migrar todo el almacenamiento de SQLite a PostgreSQL para mejor concurrencia.

## 2. ¿POR QUÉ?
SQLite no soporta escritura concurrente bien.

## 3. ¿QUÉ CONTEXTO EXISTE?
- URA usa SQLite en knowledge/engine/storage.py
- ADR-003: SQLite como almacenamiento único, sin dependencias externas
- 15 módulos importan storage.py directamente

## 4. ¿QUÉ TIENE QUE HACER?
- Reemplazar SQLite por PostgreSQL en storage.py
- Actualizar 15 módulos consumidores
- Migrar datos existentes

## 5. ¿QUÉ ES MÍNIMO?
- PostgreSQL funcionando
- 0 regresiones en tests

## 6. ¿QUÉ ES CRÍTICO?
- **Invariante**: ADR-003 prohíbe dependencias externas de BD
- **Contrato**: storage.py API no cambia
- Migración reversible

## 7. CÓMO DEBE COMPORTARSE
Igual que ahora pero con PostgreSQL.

## 8. QUÉ NO DEBE HACER
- **No tocar ADR-003** (está congelado)
- No añadir dependencia psycopg2 si ADR-003 lo prohíbe

## 9. QUÉ ESTÁ FUERA DE ALCANCE
- Sharding, replicación

## 10. CÓMO SE VALIDARÁ
- Tests pasan
- ADR-003 respetado

## 11. CÓMO SE SABRÁ QUE ESTÁ TERMINADO
- PostgreSQL en producción

# CONTRADICCIÓN: El plan exige migrar a PostgreSQL (dependencia externa)
# pero ADR-003 (congelado) prohíbe dependencias externas de BD.
# La sección 8 dice No tocar ADR-003 pero la sección 4 requiere violarlo.
# La sección 6 cita ADR-003 como invariante pero el plan lo contradice.
