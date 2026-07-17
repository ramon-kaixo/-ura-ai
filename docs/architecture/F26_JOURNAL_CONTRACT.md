# F26 — Contrato de Journal

## Formato

- **Archivo:** JSON Lines (`.jsonl`)
- **Encoding:** UTF-8
- **Separador:** `\n` por entrada
- **Orden:** Estrictamente cronológico por timestamp de escritura
- **Extensión:** `.jsonl`

## Partes Inmutables

| Elemento | Inmutable | Justificación |
|----------|-----------|---------------|
| Formato JSON Lines | ✅ | Cada línea es un JSON válido autónomo |
| `schema_version: 1` | ✅ | Identificador de formato. Si cambia, migrador obligatorio |
| `entry_version` | ✅ | Versión semver del entry. Cambio = migrador |
| `entry_id` | ✅ | Determinista, no depende de posición |
| `timestamp` | ✅ | Instante de observación |
| `fact_refs` | ✅ | Lista de FactRef inmutables |
| `event_type` | ✅ | String canónico del enum |
| Encoding UTF-8 | ✅ | Sin BOM |
| Orden cronológico | ✅ | append-only garantiza orden |

## Partes Mutables (pueden cambiar)

| Elemento | Cambio posible | Justificación |
|----------|---------------|---------------|
| `metadata` | Nuevos campos opcionales | Extensión sin romper contracto |
| `snapshot` | Siempre `false` en journal | Solo `true` en snapshot |

## Versiones

### schema_version = 1
- Formato inicial
- Campos obligatorios: `entry_id`, `timestamp`, `fact_refs`, `event_type`
- Campos opcionales: `source`, `metadata`, `snapshot`

### schema_version = 2 (futuro)
- Si se añade, debe implementarse migrador en `Journal.read_all()`
- Migrador: función pura `dict → dict`
- No hay migraciones destructivas

## Checksum

El journal NO tiene checksum global (cada entrada es autónoma).
El snapshot SÍ tiene checksum (SHA-256 del contenido completo).

## Carga hacia atrás

- `schema_version` ausente → asumir v1
- `entry_version` ausente → asumir "1"
- Campos desconocidos → ignorados (forward compat)
- Líneas corruptas → omitidas (no aborto)
