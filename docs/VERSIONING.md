# Versionado Semántico — Knowledge Engine

## Esquema

```
MAJOR.MINOR.PATCH
```

| Componente | Cuándo incrementar | Ejemplo |
|---|---|---|
| **MAJOR** | Ruptura de contrato (CLI, schema, determinism ABI, manifest, NDJSON, API.md) | `1.0.0`, `2.0.0` |
| **MINOR** | Nueva funcionalidad compatible | `0.3.0`, `0.4.0` |
| **PATCH** | Bugfix, seguridad, rendimiento | `0.2.1`, `0.2.2` |

## Contratos congelados (requieren MAJOR)

| Contrato | Archivo | Estable desde |
|---|---|---|
| CLI commands | `docs/api/API.md` | v0.2.0 |
| SQLite schema | `schemas/knowledge_graph.sql` | v0.2.0 |
| Determinism ABI | `knowledge/engine/determinism.py` | v0.2.0 |
| Manifest archive | `docs/api/API.md` (formato) | v0.2.0 |
| NDJSON audit | `docs/api/API.md` (formato) | v0.2.0 |
| Invariants | `docs/architecture/INVARIANTS.md` | v0.2.0 |

## Política de ramas

```
main ← protejido: solo merge via PR con CI verde
  └── feature/* ← nueva funcionalidad
  └── fix/* ← bugfix
  └── rc/* ← release candidate
```

## Política de CI

Todo PR debe pasar:
```
scripts/ci.sh  → 5 checks + invariants arquitectónicos
```
Sin excepciones.

## Política de compatibilidad

| Elemento | Compatibilidad |
|---|---|
| CLI | Compatible durante toda la rama 0.2.x |
| API.md | No se rompe salvo cambio de versión mayor |
| Schema SQLite | Solo mediante migraciones hacia delante |
| Determinism ABI | Nunca cambia dentro de la misma versión mayor |
| Manifest de archivado | Versionado explícito (`version` field) |
| NDJSON Audit | Añadir campos sí; renombrar o eliminar, no |

## Reglas para Fase E (nuevas capacidades)

### Principio
> Las nuevas capacidades deben vivir en módulos nuevos.
> Las interfaces existentes (Protocol, backends, servicios, evaluadores) son los puntos de extensión.
> Si una funcionalidad nueva obliga a modificar varios módulos del núcleo, la arquitectura de esa funcionalidad debe replantearse.

### Criterio de aceptación (4 preguntas)
1. **¿Rompe algún contrato congelado?** → Si sí, requiere nueva versión mayor o migración explícita.
2. **¿Añade una dependencia hacia una capa superior?** → Si sí, se rechaza.
3. **¿Necesita modificar más de un componente del núcleo?** → Si sí, justificar mediante un ADR.
4. **¿Puede implementarse usando interfaces existentes?** → Si sí, no debe tocar el núcleo.

## Síntomas de alerta en Fase E (detectados por CI)

- `rules.py` importa `orchestrator.py`
- `recommendation.py` escribe en SQLite
- `reader.py` deja de ser exclusivamente lectura
- Aparecen nuevos `sqlite3.connect()` fuera de `connection.py`
- Se modifica el algoritmo de determinismo sin crear `sha256-v2`
- Se añaden columnas al esquema sin migración correspondiente
- Nuevos módulos sin ADR cuando afectan a la arquitectura

## ENGINE_VERSION

Definido en `knowledge/engine/migrations.py`:
```python
ENGINE_VERSION = "0.2.0"
```

Se actualiza manualmente en cada release.
