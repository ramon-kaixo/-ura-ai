# 🏛️ ARQUITECTURA DE REFACTORIZACIÓN URA — Documento Permanente

**Versión:** 1.0  
**Fecha:** 2026-06-03  
**Autor:** Comité de los Cuatro Expertos (👮, 🦞, 🧩, ⚡)  
**Propósito:** Definir el pipeline de refactorización automática para siempre.

---

## 1. Pipeline Definitivo

```
[107+ funciones >80 líneas]
         │
         ▼
┌─────────────────────────────────────────────┐
│ 0. Contexto Dinámico (CPU, ms)               │
│    ajustar_contexto.py                       │
│    Corta num_predict = tokens × 1.5          │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 1. Poda Mecánica (CPU, ms)                  │
│    poda_mecanica.py                         │
│    ruff F841/F401/F811 + strip inline       │
│    + mapa cromático 🔴🟢                    │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 2. REFACTOR PRINCIPAL                       │
│    deepseek-coder:6.7b (3.8GB, ~25s)        │
│    4 workers en paralelo                    │
│    Tasa éxito: ~62.5%                       │
│    Prompt de 6 capas (identidad, contexto,  │
│    objetivo, restricciones, formato, check) │
└─────────────────────────────────────────────┘
         │
    ┌────┴────┐
    ✅         ❌
   ~67 OK     ~40 fallan
    │          │
    │          ▼
    │   ┌─────────────────────────────────────┐
    │   │ 3. FALLBACK                         │
    │   │    qwen2.5-coder:14b (9GB, ~120s)   │
    │   │    Solo las que fallaron con 6.7B   │
    │   │    Tasa éxito: ~40%                 │
    │   │    → ~16 más OK                     │
    │   └─────────────────────────────────────┘
    │          │
    │          ▼
    │          ❌ ~24 siguen fallando
    │          │
    │          ▼
    │   ┌─────────────────────────────────────┐
    │   │ 4. Watermarks + Auto-Reglas         │
    │   │    .nervioso/watermarks.json        │
    │   │    auto_reglas.py las repara        │
    │   │    en el siguiente ciclo            │
    │   │    Sin LLM (determinista, CPU)      │
    │   └─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────────────┐
│ 5. Compactadora Cromática                    │
│    compactadora.py                          │
│    Verifica:                                │
│    ☐ compile() del código final             │
│    ☐ Firmas AST (mismos argumentos)         │
│    ☐ Mapa 🔴 (mismas instrucciones lógicas) │
│    ☐ Contabilidad de tokens (±10%)          │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 6. Auto-Reglas (reparación determinista)    │
│    auto_reglas.py                           │
│    9 reglas built-in:                       │
│    • import os, json, sys, re, time...      │
│    • from pathlib import Path               │
│    • from typing import Optional, List...   │
│    • from datetime import datetime          │
│    Auto-aprendizaje: patrones ≥3 ciclos     │
│    → nuevas reglas con confianza 0.5+       │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 7. 10 Inspectores Paralelos (120 checks)    │
│    inspectores.py                           │
│    10 × 12 checks en ThreadPoolExecutor     │
│    Si errores → watermark → no escribe      │
│    Si OK → escribe + ruff --fix + format    │
│    Acción: 0 errores=OK, 1-4=REPAIR, 5+=   │
│    ROLLBACK                                 │
└─────────────────────────────────────────────┘
         │
         ▼
┌─────────────────────────────────────────────┐
│ 8. Tuneladora Mantenimiento (6 fases)        │
│    Cada 6 horas (tuneladora.timer)          │
│    F1: Diagnóstico + ruff fix               │
│    F2: Limpieza (cache, pycache, docker)    │
│    F3: Auditoría modelos Ollama             │
│    F4: Poda mecánica + watermarks           │
│    F5: Verificación RAM/zombies             │
│    F6: Backup snapshot                      │
└─────────────────────────────────────────────┘
```

---

## 2. Archivos del Sistema

| Archivo | Líneas | Propósito |
|---------|--------|-----------|
| `scripts/pro/refactor_large_functions.py` | ~290 | Orquestador 4 workers con fallback |
| `scripts/pro/poda_mecanica.py` | ~330 | Poda F841/F401 + cromático 🔴🟢 |
| `scripts/pro/compactadora.py` | ~310 | Inyección + verificación + contabilidad |
| `scripts/pro/inspectores.py` | ~590 | 10 inspectores, 120 checks |
| `scripts/pro/auto_reglas.py` | ~310 | 9 reglas built-in + auto-aprendizaje |
| `scripts/pro/watermark_aggregator.py` | ~190 | Memoria de errores + patrones sistémicos |
| `scripts/pro/ajustar_contexto.py` | ~120 | Ajuste dinámico de tokens LLM |
| `.config/prompts/unified_prompts.json` | — | Config unificada prompts + reglas |

---

## 3. Configuración de Modelos

| Variable | Valor | Propósito |
|----------|-------|-----------|
| `REFACTOR_MODEL` | `deepseek-coder:6.7b` | Modelo principal (rápido, código puro) |
| `REFACTOR_MODEL_FALLBACK` | `qwen2.5-coder:14b` | Fallback (preciso, para casos complejos) |
| `REFACTOR_WORKER_TOTAL` | 4 | Workers en paralelo |
| `MONSTER_THRESHOLD` | 80 | Líneas mínimas para considerar "monstruo" |
| `OLLAMA_NUM_PARALLEL` | 4 | Peticiones simultáneas a Ollama |
| `OLLAMA_MAX_LOADED_MODELS` | 4 | Modelos en memoria |

---

## 4. Tiempos Estimados (107 funciones)

| Fase | Modelo | Funciones | Tiempo | Éxito |
|------|--------|-----------|--------|-------|
| 1ª pasada | deepseek-coder:6.7b | 107 | ~12 min | ~62.5% |
| Fallback | qwen2.5-coder:14b | ~40 | ~8 min | ~40% |
| 2ª pasada | deepseek-coder:6.7b | ~20 | ~3 min | ~62.5% |
| **Total** | | **107** | **~23 min** | **~80%** |

---

## 5. Bucle de Retroalimentación

```
Cada ciclo de tuneladora (6h):
  1. Poda mecánica → encuentra funciones >80 líneas
  2. Refactor con 6.7B (rápido)
  3. Fallback con 14B (solo fallos)
  4. Compactadora + auto-reglas
  5. Inspectores (120 checks)
  6. Watermarks → si patrón ≥3 ciclos → nueva regla auto
  7. Backup + reporte

Cada 20 ciclos sin que una regla se use → se olvida
```

---

## 6. Prompt de 6 Capas para LLM

```
1. IDENTIDAD:   "Eres un ingeniero senior de Python..."
2. CONTEXTO:    "Función X (N líneas), imports disponibles..."
3. OBJETIVO:    "Divide en helpers ≤30 líneas..."
4. RESTRICCIONES: "NO cambies imports, firma, lógica..."
5. FORMATO:     "Solo código Python, sin markdown..."
6. VERIFICACIÓN: "Checklist: [ ] paréntesis, [ ] indentación..."
```

Temperatura: 0.1 (mínima creatividad)  
num_predict: tokens_reales × 1.5 (contexto dinámico)

---

## 7. Reglas Auto (Built-in)

| ID | Patrón | Reparación |
|----|--------|-----------|
| `builtin_fix_import_os` | F821: 'os' | `import os` |
| `builtin_fix_import_json` | F821: 'json' | `import json` |
| `builtin_fix_import_pathlib` | F821: 'Path' | `from pathlib import Path` |
| `builtin_fix_import_typing` | F821: 'Optional' | `from typing import Optional` |
| `builtin_fix_import_typing_list` | F821: 'List' | `from typing import List` |
| `builtin_fix_import_typing_dict` | F821: 'Dict' | `from typing import Dict` |
| `builtin_fix_import_datetime` | F821: 'datetime' | `from datetime import datetime` |
| `builtin_fix_import_subprocess` | F821: 'subprocess' | `import subprocess` |
| `builtin_fix_self` | F821: 'self' | Ignorar (falso positivo) |

---

## 8. Mapa Cromático (🔴🟢)

Generado por `poda_mecanica.py`:

- 🔴 **Roja**: fin de cada instrucción lógica (función, clase, statement)
- 🟢 **Verde**: gaps de formato entre bloques (PEP 8)

La compactadora verifica que el número de 🔴 se mantenga tras el refactor.
Si el LLM eliminó o añadió instrucciones, el mapa no cuadra y se rechaza.

---

*Este documento es permanente. No debe ser eliminado ni modificado sin consentimiento del Comité.*
