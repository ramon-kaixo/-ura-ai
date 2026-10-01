Sincroniza el código entre Mac y GX10.

Variables de entorno requeridas:
- URA_SYNC_SRC: origen (ej: /Users/ramonesnaola/URA/ura_ia_1972/ en Mac)
- URA_SYNC_DST: destino (ej: ramon@100.72.103.12:/home/ramon/URA/ura_ia_1972/ en GX10)

Ejecuta:
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' --exclude='node_modules' --exclude='*.pyc' \
  "${URA_SYNC_SRC:-/Users/ramonesnaola/URA/ura_ia_1972/}" \
  "${URA_SYNC_DST:-ramon@100.72.103.12:/home/ramon/URA/ura_ia_1972/}"
```

Después ejecuta en destino:
```bash
ssh "${URA_SYNC_SSH:-ramon@100.72.103.12}" "cd ${URA_SYNC_DST_DIR:-/home/ramon/URA/ura_ia_1972} && git add -A && git status --short"
```

Muestra el resultado de la sincronización y el estado en destino.
