Ejecuta la suite de tests completa del proyecto URA.

En Mac: `python3 -m pytest tests/ -m "mac or anywhere" -q --tb=short --timeout=30`
En GX10: `ssh ramon@100.72.103.12 "cd /home/ramon/URA/ura_ia_1972 && python3 -m pytest tests/ -m 'gx10 or anywhere' -q --tb=short --timeout=30"`

Muestra el resumen: passed, failed, skipped, xfailed.
Si hay fallos, analiza la causa raíz y propón corrección.
