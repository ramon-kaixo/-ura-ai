Sincroniza el código de Mac a GX10.

Ejecuta: `rsync -avz --exclude='.git' --exclude='__pycache__' --exclude='.venv' --exclude='node_modules' --exclude='*.pyc' /Users/ramonesnaola/URA/ura_ia_1972/ ramon@100.72.103.12:/home/ramon/URA/ura_ia_1972/`

Después ejecuta en GX10: `ssh ramon@100.72.103.12 "cd /home/ramon/URA/ura_ia_1972 && git add -A && git status --short"`

Muestra el resultado de la sincronización y el estado en GX10.
