# /parallel-status — Muestra estado de trabajo paralelo

## Rama actual
```
Rama: $(git branch --show-current)
Nodo: $(cat .opencode/.current-node-id 2>/dev/null || echo "unknown")
```

## Últimos commits de cada rama

### feature/opencode-gx10
```
git log origin/feature/opencode-gx10 --oneline -5 2>/dev/null || echo "rama no disponible"
```

### feature/opencode-web
```
git log origin/feature/opencode-web --oneline -5 2>/dev/null || echo "rama no disponible"
```

### feature/opencode-mac
```
git log origin/feature/opencode-mac --oneline -5 2>/dev/null || echo "rama no disponible"
```

## Behind main
```
git rev-list HEAD..origin/main --count 2>/dev/null || echo "0"
```

## Conflictos pendientes
```
[ -f CONFLICT.log ] && cat CONFLICT.log || echo "Sin conflictos"
```

## Última sincronización
```
[ -f .opencode/last-sync ] && cat .opencode/last-sync || echo "Nunca sincronizado"
```
