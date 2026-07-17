# F26 — Modelo de Consistencia

## Garantías tras un Fallo

| Propiedad | ¿Se garantiza? | Detalle |
|-----------|---------------|---------|
| **Durability** | ✅ | `Journal.append()` ejecuta `flush()` + `os.fsync()` antes de retornar. Tras ACK, el entry está en disco. |
| **Atomicity** | ✅ | Snapshot: `write temp → fsync → os.replace → fsync dir`. La operación es todo-o-nada. Journal: append-only, cada entrada es atómica. |
| **Consistency** | ✅ | `_recover()` carga snapshot (verificado por checksum) + replay journal (omitiendo líneas corruptas). El resultado es determinista. |
| **Recovery** | ✅ | `Memory(snapshot_path, journal_path, auto_recover=True)` reconstruye el estado completo. Verificado por benchmark (< 3s para 10K entries). |

## Detalle por Subsistema

### Journal
- Append es atómico por línea (JSON por línea)
- `flush()` + `fsync()` garantizan que la línea está en disco antes del ACK
- Líneas corruptas se omiten durante recovery (no aborto)
- Journal se rota atómicamente con cada snapshot (`os.rename`)

### Snapshot
- Escritura a archivo temporal + `fsync` + `os.replace` (atómico en POSIX)
- `fsync` del directorio padre garantiza que el rename es persistente
- Checksum SHA-256 en el header verifica integridad
- Snapshot corrupto → recovery desde journal (pérdida mínima)

### Timeline
- Append: lock exclusivo, sin estados intermedios visibles
- Consultas: entries inmutables, thread-safe
- state_at(): determinista con tie-breaking por entry_id

## Límites

- No se garantiza durabilidad si el sistema de archivos no respeta `fsync` (ej: ciertos SSD con write-back cache)
- No se garantiza recuperación si el snapshot y el journal se pierden simultáneamente
- No hay replicación en F26 (prevista para futura versión distribuida)
