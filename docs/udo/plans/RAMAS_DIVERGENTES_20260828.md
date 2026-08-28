# Decisiones de ramas divergentes — Plan 1010 (R7 + Sug.2)

Fecha: 2026-08-28
Estado: **PENDIENTE DECISIÓN HUMANA**
Clasificación: R7 (bloqueado) + Sug.2 (documentar)

## Contexto

La auditoría del Plan 1010 (P1-P6) dejó 3 ramas **locales en GX10** que divergieron
mucho de `main`. Ninguna existe en GitHub (`git ls-remote --heads origin` solo muestra `main`).
Mergarlas directamente a `main` es **destructivo**: el merge de `mac-veredictos` habría
borrado 1036 archivos (~287k eliminaciones).

## Estado (medido 2026-08-28 en GX10)

| Rama | ahead vs main | behind vs main | archivos diff | último commit |
|------|--------------|----------------|---------------|---------------|
| `merge-fase5` | 1056 | 2750 | 1940 | `f96ba531` 2026-08-01 (propuesta Fase 5) |
| `ramon/fase-1-excavacion` | 1155 | 2750 | 1796 | `bd996c7c` 2026-08-02 (attic .bak) |
| `mac-veredictos` | 2839 | 2750 | 1036 | `233236a8` 2026-08-23 (veredictos Escritorio) |

Nota: `behind = 2750` en las tres → todas parten de un commit anterior al actual `main`,
que avanzó ~2750 commits desde su bifurcación. Son ramas de trabajo del TERM/WEB previas a
la adopción del flujo actual (PR → `main` protegido).

## Contexto UDO

- `mac-veredictos` era la zona de trabajo del **TERM (Escritorio)** antes del modelo dual.
  Contiene veredictos de revisor (`[TERM] veredictos revisor desde Escritorio`).
- `merge-fase5` y `ramon/fase-1-excavacion` son ramas de trabajo de fases previas (Fase 5/1)
  anteriores a la consolidación del pipeline actual.

## Decisiones posibles (elegir UNA por rama)

1. **Archivar** (recomendado): crear tag `attic/<rama>-<fecha>` y borrar la rama local.
   El contenido queda preservado en el tag, fuera del historial activo de `main`.
   Comando: `git tag attic/merge-fase5-20260828 merge-fase5 && git branch -D merge-fase5`
   (una vez, tras **respaldo**, ver §Respaldo).
2. **Sacar contenido útil**: si alguna rama tiene archivos/veredictos únicos que valga la
   pena conservar, extraerlos a `main` de forma selectiva (cherry-pick o copia manual)
   ANTES de archivar. La auditoría determinó que `mac-veredictos` ya fue consolidado en
   `docs/udo/` (su contenido no es único).
3. **Ignorar**: dejarlas como están (sin tocar). Riesgo: siguen sin push a ningún lado y
   confunden el estado del repo.

## Respaldo previo (seguro, no destructivo)

```bash
# GX10 only — preserva ramas como bundles antes de cualquier borrado
cd /home/ramon/URA/ura_ia_1972
mkdir -p /home/ramon/URA/backups/ramas_20260828
for b in merge-fase5 ramon/fase-1-excavacion mac-veredictos; do
  git bundle create /home/ramon/URA/backups/ramas_20260828/${b}.bundle $b
done
ls -lh /home/ramon/URA/backups/ramas_20260828/
```

## Responsable

**HUMANO (Ramón)** — decisión irreversible (borrado de ramas locales). El agente NO debe
ejecutarla sin autorización expresa (regla UDO §5.19 + Regla Principal de cierre con
acciones humanas).

## Sugerencia derivada (Sug.2)

- Formalizar una **política de ramas**: solo `main` (protegida, PR) + `ia/TASK-*` activas.
  Las ramas de fases cerradas deben archivarse con tag `attic/` y borrarse, sin dejarlas
  huérfanas locales. Esto evita que divergencias de 1000+ commits se acumulen sin visibilidad.
