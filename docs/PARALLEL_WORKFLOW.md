# Trabajo Paralelo — Workflow Multi-Nodo

## Visión General

URA permite que 3 instancias de OpenCode trabajen simultáneamente sobre el mismo repositorio:

| Nodo | Rama | Máquina |
|------|------|---------|
| `gx10-desktop` | `feature/opencode-gx10` | GX10 (100.72.103.12) |
| `gx10-web` | `feature/opencode-web` | GX10 (100.72.103.12:8081) |
| `mac` | `feature/opencode-mac` | Mac Mini (100.123.81.101) |

## Setup Inicial (una vez por máquina)

```bash
# 1. Configurar nodo
echo "URA_NODE_ID=mac" >> ~/.ura/secrets.env  # o gx10-desktop, gx10-web

# 2. Inicializar rama
./scripts/pro/parallel-branch-init.sh

# 3. Instalar pre-commit hook
cp .git/hooks/pre-commit .git/hooks/pre-commit.bak 2>/dev/null
# El hook ya está en .git/hooks/pre-commit
```

## Flujo Diario

### 1. Sincronizar al inicio
```bash
./scripts/pro/parallel-sync.sh
```

### 2. Trabajar normalmente
Cada nodo trabaja en su rama `feature/opencode-{nodo}`. El pre-commit hook previene conflictos de archivos.

### 3. Sincronizar periódicamente
```bash
# Cada 30 min (cron o manual)
./scripts/pro/parallel-sync.sh
```

### 4. Integrar ramas
```bash
# Cada 6h o bajo demanda
./scripts/pro/parallel-merge-driver.sh --auto
```

### 5. Verificar estado
```bash
# Desde cualquier nodo
curl http://localhost:4097/parallel/status
# O usar el comando /parallel-status
```

## Resolución de Conflictos

Cuando `parallel-sync.sh` detecta conflictos:
1. Escribe `CONFLICT.log` con detalles
2. Detiene la sincronización
3. Resuelva manualmente:
   ```bash
   git rebase origin/develop
   # Resolver conflictos en archivos
   git add .
   git rebase --continue
   ```
4. Si `--auto` está activo, se crea una tarea en TaskQueue tipo `CONFLICT_RESOLUTION`

## Pre-commit Hook

El hook verifica `parallel-lock.json` en `.opencode/`. Si otro nodo tiene lock sobre un archivo que estás modificando, el commit se bloquea con:
```
[BLOCKED] Archivo 'X' está bloqueado por nodo 'Y'
[BLOCKED] Sincroniza primero: ./scripts/pro/parallel-sync.sh
```

## Merge Driver

Orden de merge: `gx10` → `web` → `mac`. Cada rama se integra a `develop` con `--no-ff`.

Si falla con `--auto`, se crea tarea `CONFLICT_RESOLUTION` automáticamente.

## API Endpoint

`GET /parallel/status` devuelve:
```json
{
  "node_id": "mac",
  "branch": "feature/opencode-mac",
  "behind_develop": 3,
  "has_conflicts": false,
  "other_branches": {
    "feature/opencode-gx10": {"commits": ["abc1234 fix: ..."]},
    "feature/opencode-web": {"commits": ["def5678 feat: ..."]}
  }
}
```

## Restricciones

- **NO** hacer push directo a `main` (branch protection activo)
- **NO** merge `develop` → `feature/*` manualmente (usar `parallel-sync.sh`)
- Cada nodo solo modifica archivos en su rama
- Si un archivo es crítico (ej. `failover.py`), crear PR en vez de merge directo
