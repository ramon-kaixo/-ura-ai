# REPO_HYGIENE — Auditoría de Peso del Repositorio (Fase 1.4)

**Fecha:** 2026-08-02
**Rama:** `main`
**Estado:** ✅ Documentado (decisión: no reescribir historia, ver Conclusiones)

## Datos reales

| Métrica | Valor |
|---------|-------|
| Working tree (`du -sh .`) | 1,3 GB |
| `.git/` | 144 MB (size-pack 22,93 MiB, 6.907 objetos) |
| Blobs > 1 MB en historia | 12 |
| Total blobs > 1 MB | 56 MB |

## Blobs grandes en historia Git (12)

| Tamaño | Archivo | Tipo |
|--------|---------|------|
| 10,36 MB | `core/modules/data/chroma_db_code/chroma.sqlite3` | BD vectorial (5 versiones: 10,3 / 10,3 / 8,0 / 7,7 / 6,7 MB) |
| 4,8 MB | `.../c89337fc-.../data_level0.bin` | Cache Chroma (×2 versiones) |
| 2,27 MB | `data/baseline/coverage_f4.json` | JSON de cobertura (×2 versiones) |
| 2,23 MB | `data/voz/grabaciones/sesion_20260513_005121_intento_1.wav` | Audio |
| 1,31 MB | `motor_deps.svg` | Diagrama |
| 1,06 MB | `core_deps.svg` | Diagrama |

## Diagnóstico

1. **chroma.sqlite3 (5 versiones, ~43 MB acumulados)**: base de datos vectorial
   commiteada por error al repo. Debería estar en `.gitignore` o en volumen de
   datos externo (`data/`). Es regenerable (indexación de embeddings).
2. **coverage_f4.json (2 versiones)**: artefacto de medición regenerable —
   no debería versionarse en git (ya existe la convención de `data/baseline/`).
3. **WAV de voz**: grabación de sesión, contenido personal — candidata a borrar.
4. **SVGs**: diagramas generados por scripts — regenerables.

## Qué pesa 1,3 GB en working tree (no es historia Git)

La mayor parte del peso NO está en git (144 MB de `.git`): son datos locales
ignorados (`data/`, modelos, caches, `.venv`, `.sandbox_packages`, `.nervioso`).
Verificado: blobs git totales = 56 MB + compresión = 22,93 MiB pack.

## Acciones recomendadas (diferidas — no ejecutadas)

| Acción | Impacto | Riesgo |
|--------|---------|--------|
| `git filter-repo` para chroma.sqlite3 + WAV | −43 MB historia | REESCRIBE historia; invalida hashes; requiere coordinación |
| `git rm --cached chroma.sqlite3` + añadir a .gitignore | deja de crecer | Bajo; los blobs siguen en historia pero no se añaden más |
| `git rm --cached data/voz/*.wav` + .gitignore | deja de crecer | Bajo |
| Git LFS para binarios | −43 MB pack | Requiere `git-lfs` instalado; cambio de flujo |

## Decisión adoptada

**Solo documentar** (decisión del operador, 2026-08-02). No se ejecuta
`git filter-repo` ni `git lfs migrate` por ser operaciones irreversibles que
reescriben historia. El repo es single-user pero los hashes sirven de referencia
a la entidad paralela activa en `main`.

Acción de bajo riesgo permitida a futuro: `git rm --cached` de los binarios +
añadir a `.gitignore` para evitar que el problema crezca, previa confirmación.

## Verificación reproducible

```bash
git rev-list --objects --all | git cat-file --batch-check='%(objecttype) %(objectname) %(objectsize) %(rest)' \
  | awk '$1=="blob" && $3 > 1048576 {print $3, $4}' | sort -rn | head -12
git count-objects -vH
du -sh .git .
```
