# META — Plantilla de zona (índice de conocimiento por carpeta)

Propósito: cuando un agente va a tocar una carpeta/zona, lee su META antes de
abrir archivos. Se actualiza al cerrar toda TASK que toque la zona
(1 línea nueva por archivo tocado, con fuente TASK/commit).

## Formato

```
# META: <ruta de la zona>

## Idea de desarrollo
2-4 líneas: por qué existe esta zona, cuál fue su propósito original.

## Archivos
| Archivo | Qué hace | Errores conocidos (arreglo, fuente) | Idea original |
|---------|----------|--------------------------------------|---------------|
| ruta/archivo.py | 1 línea de función real | errores con commit/TASK | por qué se creó |

## Historia de la zona (bitácora breve)
- YYYY-MM-DD: evento (fuente: TASK/commit)
```

## Reglas de mantenimiento
1. NO inventar: cada afirmación de errores/arreglos lleva fuente (TASK o SHA).
2. Añadir, no reescribir: la historia es acumulativa (append).
3. Zonas grandes: un META por submódulo (ej. core/mochila/, motor/core/llm/).
4. Al cerrar una TASK que tocó una zona sin META → crearlo con 1 fila mínima.
