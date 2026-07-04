# Determinism ABI — Knowledge Engine

**Version:** sha256-v2
**Date:** 2026-07-01
**Status:** Frozen (changes require MAJOR version bump)

## Algorithm

```
H = SHA-256(JSON_canonical({"nodes": N, "edges": E}))
```

Where `JSON_canonical` = `json.dumps(data, sort_keys=True)` with Python's default separators and `ensure_ascii=True`.

## Input: Nodes (N)

### SQL
```sql
SELECT id, type, path, content_sha256, body, frontmatter, quality, confidence
FROM kg_nodes
ORDER BY id
```

### Columns included
| Column | Type | Notes |
|---|---|---|
| `id` | TEXT | Deterministic: SHA-256(path)[:12] |
| `type` | TEXT | From frontmatter `type` field |
| `path` | TEXT | Relative file path |
| `content_sha256` | TEXT | SHA-256 of raw file bytes (UTF-8, LF, no BOM) |
| `body` | TEXT | Markdown body text |
| `frontmatter` | TEXT | JSON serialized with `sort_keys=True` |
| `quality` | REAL | From document parse |
| `confidence` | REAL | From document parse |

### Columns excluded (v2)
| Column | Reason |
|---|---|
| `embed_hash` | Always NULL. Removed in v2 to prevent future breakage. |
| `semantic` | Embedding-derived, may vary between runs |
| `updated_at` | Timestamp, non-deterministic |

## Input: Edges (E)

### SQL
```sql
SELECT src, dst, relation
FROM kg_edges
ORDER BY src, dst, relation
```

## Normalization

| Aspect | Rule |
|---|---|
| Line endings | LF only (content bytes stored as-is) |
| Encoding | UTF-8 without BOM |
| JSON serialization | `json.dumps(sort_keys=True)`, default separators, default `ensure_ascii=True` |
| Dict order | Python 3.7+ insertion order preserved (guaranteed by `sort_keys=True` at hash time) |
| Floating point | SQLite REAL stored/retrieved as-is (IEEE 754) |
| NULL handling | SQL NULL becomes JSON `null` via `dict(row)` |
| ORDER BY | Explicit: `kg_nodes.id`, `kg_edges.src, dst, relation` |
| Timestamps | Excluded from hash input |

## Output

- **Algorithm:** SHA-256
- **Encoding:** hex (lowercase)
- **Length:** 64 characters
- **Storage:** `kg_active_version.determinism_hash`
- **Algorithm version:** `kg_active_version.determinism_algorithm` = `"sha256-v2"`

## Compatibility

| Version | Algorithm | Changes |
|---|---|---|
| `sha256-v1` | SHA-256 with `embed_hash` included | Original (Fase A/B) |
| `sha256-v2` | SHA-256 without `embed_hash` | Current (Fase D+. `embed_hash` was always NULL) |

## Testing

```python
# Must hold for any input:
compile(source) → hash1
compile(source) → hash2
assert hash1 == hash2  # Same input → same hash

compile(source_a) → hash_a
compile(source_b) → hash_b
assert hash_a != hash_b  # Different input → different hash
```
