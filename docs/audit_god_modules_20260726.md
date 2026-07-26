# Auditoría God Modules — 2026-07-26
# SOLO DIAGNÓSTICO. Sin refactorización.

## Hallazgos

### 1. core/model_router.py — 1,274 líneas

| Métrica | Valor | Umbral | Estado |
|---------|-------|--------|--------|
| Total líneas | 1,274 | <500 | ❌ 2.5x |
| Funciones >50 líneas | 2 | 0 | ❌ |
| Clases >200 líneas | 1 (RouterHandler, 338 líneas) | 0 | ❌ |

**Funciones problemáticas:**
-  (línea 603, 51 líneas)
-  (línea 1133, 78 líneas)

**Clase problemática:**
-  (línea 876, 338 líneas)

### 2. core/mochila/mochila_server.py — 752 líneas

| Métrica | Valor | Umbral | Estado |
|---------|-------|--------|--------|
| Total líneas | 752 | <500 | ❌ 1.5x |
| Funciones >50 líneas | 3 | 0 | ❌ |
| Clases >200 líneas | 0 | 0 | ✅ |

**Funciones problemáticas:**
-  (línea 306, 82 líneas)
-  (línea 446, 83 líneas)
-  (línea 564, 82 líneas)

### 3. mochila_engine.py — 223 líneas

| Métrica | Valor | Umbral | Estado |
|---------|-------|--------|--------|
| Total líneas | 223 | <500 | ✅ |
| Funciones >50 líneas | 0 | 0 | ✅ |
| Clases >200 líneas | 0 | 0 | ✅ |

## Circular Dependencies

-  → 
-  → 
-  → 
-  → 

## Recomendaciones (futuro)

### model_router.py
1. Extraer  → 
2. Extraer  → 

### mochila_server.py
1. Extraer  → 
2. Extraer  → 
