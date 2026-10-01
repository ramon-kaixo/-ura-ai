Sincroniza el código entre Mac y GX10.

Variables de entorno requeridas:
- URA_SYNC_SRC: origen (ej: /Users/ramonesnaola/URA/ura_ia_1972/ en Mac)
- URA_SYNC_DST: destino (ej: ramon@100.72.103.12:/home/ramon/URA/ura_ia_1972/ en GX10)

Ejecuta:
```bash
rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' --exclude='node_modules' --exclude='*.pyc' \
  "${URA_SYNC_SRC:?Error: URA_SYNC_SRC no definida}" \
  "${URA_SYNC_DST:?Error: URA_SYNC_DST no definida}"
```

Después ejecuta en destino:
```bash
ssh "${URA_SYNC_SSH:?Error: URA_SYNC_SSH no definida}" "cd ${URA_SYNC_DST_DIR:?Error: URA_SYNC_DST_DIR no definida} && git add -A && git status --short"
```

Muestra el resultado de la sincronización y el estado en destino.
