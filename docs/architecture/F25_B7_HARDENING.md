# F25-B7: Hardening de FactHistory

**Fecha:** 2026-07-17  
**Depende de:** ADR-025-02, ADR-025-03, ADR-025-04, F25-B6

---

## 1. Contrato de Complejidad (R07-05)

Complejidades temporales garantizadas de FactHistory:

| Operación | Complejidad | Contrato |
|-----------|-------------|----------|
| `create(fact, version)` | O(1) | Construye estructura + valida fact_id match |
| `add_version(version)` | O(1) + O(1) para SUPERSEDE | Inserción en dict + actualización current |
| `rollback(version_id)` | O(1) | Reasigna current + marca versiones |
| `tombstone(version)` | O(1) | Similar a add_version con estado TOMBSTONE |
| `current` (property) | O(1) | Lookup en dict por current_version_id |
| `get_version(vid)` | O(1) | Lookup en dict |
| `timeline()` | O(n) | Sort de versiones por created_at (n = número de versiones) |
| `version_at(timestamp)` | O(k) | Recorrido de cadena supersedes (k <= n, típicamente O(1)) |
| `to_dict()` | O(n) | Copia de todas las versiones |
| `from_dict()` | O(n log n) | Sort de versiones + reconstrucción |

### Invariantes de complejidad

```
C1. add_version() nunca degrada por acumulación de versiones
C2. current property nunca degrada (siempre O(1))
C3. timeline() es O(n) y solo se llama explícitamente (no en hot path)
C4. version_at() es O(k) donde k es la distancia desde current
C5. rollback() no depende del número de versiones
```

---

## 2. Política de Migración (R07-09)

### Schema versioning

```
FACT_HISTORY_SCHEMA_VERSION = 1
```

El schema version se almacena como metadato en la serialización:

```python
{
    "schema_version": 1,
    "fact_id": "...",
    "current": "...",
    "versions": {...},
    "tombstones": {...},
    "created": ...,
    "updated": ...
}
```

### Migración N → N+1

1. La función `from_dict()` detecta `schema_version` y aplica transformaciones.
2. Cada migración se implementa como una función pura: `dict → dict`.
3. No hay migraciones destructivas (siempre se preservan datos originales).
4. Si no hay `schema_version`, se asume versión 1.

```python
_MIGRATIONS: dict[int, Callable[[dict], dict]] = {
    # 1 → 2: ejemplo de migración futura
    # 2: lambda d: {**d, "new_field": d.get("old_field", default)}
}

def _apply_migrations(data: dict, target_version: int = FACT_HISTORY_SCHEMA_VERSION) -> dict:
    current = data.get("schema_version", 1)
    while current < target_version:
        migrator = _MIGRATIONS.get(current)
        if migrator:
            data = migrator(data)
        current += 1
    data["schema_version"] = target_version
    return data
```

### Compatibilidad hacia atrás

- `from_dict()` debe aceptar datos sin campo `state` (asumir CURRENT).
- `from_dict()` debe aceptar datos sin `schema_version` (asumir v1).
- `from_dict()` nunca debe lanzar excepción por campos desconocidos.
- Los checksums históricos se recalculan siempre desde los datos actuales.

---

## 3. Recuperación ante Fallos (R07-12)

### Durante serialización

| Fase | Riesgo | Recuperación |
|------|--------|-------------|
| `to_dict()` | Error de memoria OOM | No hay recuperación parcial (todo o nada). El historial original no se modifica. |
| `from_dict()` | Datos corruptos | Validación previa con schema_version. Si falla, se retorna el error (no se reconstruye parcialmente). |
| Escritura a disco (futuro) | Escritura incompleta | Usar write-ahead log (WAL) + atomic rename. |

### Invariantes de recuperación

```
R1. to_dict() es pura: no muta el historial original.
R2. from_dict() es atómica: o reconstruye completamente o lanza excepción.
R3. El historial original no se pierde aunque from_dict() falle (inmutabilidad de FactVersion).
R4. Tras from_dict() exitoso, todas las invariantes V01-V10 se mantienen.
```

---

## 4. Resumen de Tests de Hardening

| ID | Test | Tipo | Cubre |
|----|------|------|-------|
| H01 | `test_concurrent_readers_during_add` | Concurrencia | R07-01, R07-02 |
| H02 | `test_concurrent_rollback_during_reads` | Concurrencia | R07-01, R07-02 |
| H03 | `test_fuzz_random_operations` | Fuzz (50 trials × 10-200 ops) | R07-03 |
| H04 | `test_corruption_nonexistent_current` | Corrupción | R07-04 |
| H05 | `test_corruption_broken_supersedes_chain` | Corrupción | R07-04 |
| H06 | `test_corruption_cycle_in_supersedes` | Corrupción | R07-04 |
| H07 | `test_corruption_orphan_version` | Corrupción | R07-04 |
| H08 | `test_corruption_tombstone_rollback` | Corrupción | R07-04 |
| H09 | `test_benchmark_add_100k` | Benchmark | R07-06 |
| H10 | `test_benchmark_rollback_100k` | Benchmark | R07-06 |
| H11 | `test_benchmark_version_at_100k` | Benchmark | R07-06 |
| H12 | `test_benchmark_ram_1m` | RAM (slow) | R07-07 |
| H13 | `test_soak_million_operations` | Soak (slow) | R07-08 |
| H14 | `test_serialization_backward_compat` | Compatibilidad | R07-10 |
| H15 | `test_serialization_checksum_stability` | Checksum | R07-11 |
| H16 | `test_checksum_stable_after_same_ops` | Checksum | R07-11 |
| H17 | `test_checksum_changes_after_mutation` | Checksum | R07-11 |
| H18 | `test_fact_index_remove_legacy_fact` | FactIndex cleanup | R07-13 |
| H19 | `test_fact_index_remove_version_fact` | FactIndex cleanup | R07-13 |
| H20 | `test_rollback_preserves_timeline` | Rollback stats | R07-14 |
| H21 | `test_benchmark_zipf_distribution` | Zipf | R07-15 |
