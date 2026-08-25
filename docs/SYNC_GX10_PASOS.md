# Sync Mac → GX10 — Pasos manuales

## Pré-requisitos
- Tailscale activo en ambas máquinas (o WiFi directo)
- SSH habilitado en GX10

## Paso 1: Sync código
```bash
# En Mac:
cd /Users/ramonesnaola/URA/ura_ia_1972
rsync -avz --delete \
  --exclude='.env' \
  --exclude='__pycache__' \
  --exclude='.venv' \
  --exclude='build/' \
  --exclude='backups_gx10/' \
  --exclude='archives/' \
  --exclude='.nervioso/' \
  . ramon@100.72.103.12:/home/ramon/URA/ura_ia_1972/
```

## Paso 2: Verificar en GX10
```bash
# En GX10:
cd /home/ramon/URA/ura_ia_1972
git status  # debe estar limpio
python3 -m ruff check . --statistics | tail -3
URA_API_KEY=test python3 -m pytest tests/unit/test_mochila_server_guardian.py -q --timeout=30
```

## Paso 3: Restart servicios productivos
```bash
# En GX10:
sudo systemctl restart ura-mochila
sudo systemctl restart model-router
sudo systemctl status ura-mochila model-router  # verificar activos
```

## Paso 4: Verificar servicios funcionan
```bash
# En GX10:
curl -s http://127.0.0.1:8000/health | python3 -m json.tool
curl -s http://127.0.0.1:11435/health | python3 -m json.tool
```
