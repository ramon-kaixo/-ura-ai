# 🧠 ARQUITECTURA MULTI-AGENTE URA — Sistema Autónomo y Autoconsciente

**Versión:** 3.0
**Fecha:** 2026-06-04
**Hardware:** NVIDIA GX10 (128GB RAM unificada, 20 núcleos ARM, GPU Blackwell)
**Modelos:** Ollama local (deepseek-coder:6.7b, qwen2.5-coder:14b, qwen2.5-coder:q8_0, qwen3:32b-q8_0)

---

## 1. ARQUITECTURA DETERMINISTA Y MEMORIA

### 1.1 Estado Compartido (.nervioso/conciencia.json)

```json
{
  "estado_general": "ok",
  "nivel_error": 0,
  "ultimo_ciclo": "2026-06-04T11:31:47",
  "procesos": {
    "orquestador":   {"estado": "activo",  "ultima_accion": "delegar refactor"},
    "ejecutor":      {"estado": "idle",     "funciones_pendientes": 35},
    "reparador":     {"estado": "idle",     "reparaciones_hoy": 12},
    "token_screen":  {"estado": "activo",  "tokens_ajustados": 16146},
    "scanner":       {"estado": "idle",    "ultimo_diff": "F821 0→0"},
    "compactadora":  {"estado": "idle",    "archivos_validados": 34},
    "inspectores":   {"estado": "idle",    "ultimo_cycle": 119},
    "openclaw":      {"estado": "idle",    "veredictos_emitidos": 23},
    "chunk_optimizer":{"estado": "idle",   "chunk_actual": 22937}
  },
  "contexto_global": {
    "ultimo_archivo": "core/central_router.py",
    "ciclo_actual": 3,
    "progreso": "67/107 funciones",
    "errores_acumulados": [],
    "arreglos_aplicados": []
  }
}
```

### 1.2 Sistema de Telemetría

```
HARDWARE (cada 1s)        RED (cada 10s)        LLM (cada llamada)
├── RAM libre (psutil)    ├── Model Router :11435 ├── Tokens enviados
├── CPU idle              ├── Ollama :11434      ├── Tiempo respuesta
├── Zombies               ├── Tailscale          ├── Modelo usado
├── Disco NVMe            ├── Mac :26            └── Tasa éxito/error
└── GPU VRAM              └── 4 dispositivos

LOGS (cada ciclo)         MÉTRICAS (cada 6h)    ALERTAS (umbrales)
├── F821 delta            ├── Ruff issues        ├── RAM >90GB
├── Token divergence      ├── Funciones >80l     ├── Zombies >0
├── Tiempo ciclo          ├── Tasa éxito refactor├── Model Router DOWN
└── Archivos procesados   └── Chunk óptimo       └── F821 >baseline+10%
```

### 1.3 Capas Deterministas (CPU, sin LLM)

| Capa | Componente | Tiempo | Qué hace |
|------|-----------|--------|----------|
| **Entrada** | `token_screen.py` | ~1ms | RAM guardian + ajuste contexto |
| **Entrada** | `scanner_autoajuste.py` | ~10ms | AST snapshot (funciones, F821, hash) |
| **Pre-proceso** | `poda_mecanica.py` | ~50ms | Ruff F841/F401 + cromático 🔴🟢 |
| **Post-proceso** | `compactadora.py` | ~5ms | Inyección quirúrgica + verificación |
| **Post-proceso** | `auto_reglas.py` | ~10ms | Repara imports faltantes (9 built-in) |
| **Salida** | `scanner_autoajuste.py --diff` | ~30ms | Compara entrada vs salida |
| **Salida** | `chunk_optimizer.py` | ~1ms | Ajusta tamaño chunk según calidad |
| **Validación** | `inspectores.py` (10×12) | ~120ms | 120 checks en paralelo |
| **Estado** | `conciencia.py` | ~1ms | Actualiza memoria unificada |

**Total CPU determinista por archivo: ~228ms**

---

## 2. ROLES DEL SISTEMA MULTI-AGENTE

### 2.1 Agente Orquestador — Qwen 2.5 Coder 14B

```python
ORQUESTADOR_PROMPT = """Eres el Orquestador de URA, un sistema multi-agente autónomo.
Tu trabajo es decidir QUÉ tarea delegar a qué agente, basándote en el estado del sistema.

ESTADO ACTUAL:
  RAM: {ram}MB libre
  Modelos disponibles: {modelos}
  F821 pendientes: {f821}
  Funciones sin refactorizar: {pendientes}

AGENTES DISPONIBLES:
  1. EJECUTOR (deepseek-coder:6.7b) — Rápido, refactoriza código. 62.5% éxito.
  2. REPARADOR (auto_reglas.py) — Determinista, arregla imports. 100% éxito en su dominio.
  3. REVISOR (openclaw_reviewer, qwen2.5-coder:q8_0) — Revisa lógica, vota APROBAR/RECHAZAR.

DECISIÓN:
  Si F821 > 10 → delegar a REPARADOR (auto_reglas)
  Si funciones_pendientes > 0 y RAM < 85% → delegar a EJECUTOR (refactor 6.7B)
  Si EJECUTOR termina → delegar a REVISOR (openclaw q8_0)
  Si RAM > 85% → PAUSAR todo, esperar

Responde SOLO con una de estas acciones:
  ACCION: REPARAR
  ACCION: REFACTORIZAR
  ACCION: REVISAR
  ACCION: PAUSAR
  RAZON: <explicación breve>"""
```

### 2.2 Agente Ejecutor — DeepSeek Coder 6.7B

```python
EJECUTOR_PROMPT = """Eres el Ejecutor de URA. Refactorizas funciones grandes (>80 líneas)
en helpers atómicas (≤30 líneas) sin cambiar el comportamiento.

IDENTIDAD:
  Ingeniero senior de Python con 20 años de experiencia en refactorización.

CONTEXTO:
  Función: '{func_name}' ({n_lines} líneas)
  Los imports disponibles son los que ya están en el código.

OBJETIVO:
  Divide esta función en helpers más pequeñas (MÁXIMO 30 líneas cada una).

RESTRICCIONES:
  1. NO cambies la lógica ni el comportamiento observable
  2. NO cambies nombres de variables, argumentos, ni imports
  3. Las helpers van al MISMO nivel de indentación, nunca anidadas

FORMATO: Solo código Python. Sin markdown. Sin explicaciones.

VERIFICACIÓN: [ ] Paréntesis balanceados [ ] Indentación 4 espacios [ ] Sin bloques vacíos

[CÓDIGO]
{func_source}"""
```

### 2.3 Agente Reparador de Código — Determinista + LLM

```python
REPARADOR_PROMPT = """Eres el Reparador de URA. Recibes código con errores detectados
por el scanner y debes repararlo SIN cambiar la lógica.

ERROR DETECTADO: {error_type} en línea {line_number}
MENSAJE: {error_message}

CÓDIGO CON ERROR:
```python
{code_with_error}
```

INSTRUCCIONES:
  1. SOLO repara el error específico, no refactorices
  2. NO cambies la lógica del programa
  3. Si es un import faltante, añádelo al principio del archivo
  4. Si es una variable no definida, inicialízala con un valor razonable
  5. Devuelve SOLO el código reparado, sin explicaciones

CÓDIGO REPARADO:"""
```

**Estrategia de reparación (3 niveles):**

```
NIVEL 1 — Determinista (CPU, <10ms):
  auto_reglas.py → repara imports faltantes (os, json, Path, Optional...)
  ruff --fix → repara indentación, sintaxis básica
  Si funciona → FIN

NIVEL 2 — LLM rápido (deepseek 6.7B, ~30s):
  Envía el error + contexto al Ejecutor
  Prompt específico de reparación
  Si funciona → FIN

NIVEL 3 — LLM potente (qwen3:32b-q8_0 vía OpenCode, ~120s):
  Solo para errores complejos que fallaron en N1 y N2
  Si funciona → guardar solución en auto_reglas (aprender)
  Si falla → WATERMARK + siguiente ciclo
```

---

## 3. BUCLE DE AUTO-ARREGLO (SELF-HEALING)

### 3.1 Diagrama de flujo

```
┌──────────────────────────────────────────────────────────────────────┐
│                    BUCLE DE AUTO-ARREGLO                              │
│                                                                      │
│  ① DETECTAR                                                          │
│     Scanner SALIDA: F821 subió +3, tokens divergen 25%               │
│     → ALERTA: nivel_error = 1 (LEVE)                                │
│     → Conciencia registra: "F821 en central_router.py:120"          │
│                                                                      │
│  ② AISLAR                                                            │
│     cp central_router.py → /tmp/quarantine/central_router.bak        │
│     Sandbox: docker exec ura-mejora-continua python3 ...             │
│     → Código original seguro, cambios solo en sandbox                │
│                                                                      │
│  ③ REPARAR (3 intentos)                                              │
│     Intento 1: auto_reglas.py (determinista, CPU)                    │
│       → ¿Falta import? → añadir. compile() → ¿OK?                    │
│       ✅ SI → saltar a ④                                            │
│       ❌ NO → Intento 2                                              │
│     Intento 2: deepseek-coder:6.7b (LLM, ~30s)                      │
│       → Prompt de reparación + código con error                      │
│       → LLM devuelve código reparado                                 │
│       → compile() + scanner diff → ¿OK?                              │
│       ✅ SI → saltar a ④                                            │
│       ❌ NO → Intento 3                                              │
│     Intento 3: qwen3:32b-q8_0 vía OpenCode (LLM, ~120s)             │
│       → Prompt más detallado + contexto completo                     │
│       → LLM devuelve código reparado                                 │
│       → compile() + scanner diff → ¿OK?                              │
│       ✅ SI → guardar solución en auto_reglas (aprender)            │
│       ❌ NO → WATERMARK (siguiente ciclo)                            │
│                                                                      │
│  ④ VALIDAR                                                            │
│     compile() → ✅                                                   │
│     scanner diff → F821 entrada vs salida → ¿mejoró?                 │
│     10 inspectores (120 checks) → ✅                                  │
│     OpenClaw reviewer (q8_0) → vota APROBAR                          │
│                                                                      │
│  ⑤ ACTUALIZAR                                                        │
│     cp /tmp/quarantine/repaired.py → central_router.py               │
│     Conciencia: arreglos_aplicados += 1, nivel_error = 0             │
│     Chunk optimizer: "calidad buena" → AUMENTAR chunk                │
│                                                                      │
│  ⑥ SI FALLA (WATERMARK)                                              │
│     Guardar en .nervioso/watermarks.json:                            │
│     {archivo, error, intentos, timestamp}                            │
│     Si mismo error ≥3 ciclos → diagnosticar prompt engineering       │
│     Siguiente ciclo: prioridad alta para este archivo                │
└──────────────────────────────────────────────────────────────────────┘
```

### 3.2 Pseudocódigo del bucle

```python
def self_healing_loop(archivo):
    # 1. DETECTAR
    entrada = scanner.snapshot(archivo)
    # ... ejecutar pipeline ...
    salida = scanner.diff(archivo)
    
    if salida.paso:
        conciencia.registrar_exito(archivo)
        return True
    
    # 2. AISLAR
    backup = archivo + ".bak"
    shutil.copy(archivo, backup)
    
    # 3. REPARAR (3 niveles)
    for nivel, reparador in enumerate([
        auto_reglas,           # N1: Determinista
        deepseek_6_7b,         # N2: LLM rápido
        opencode_32b           # N3: LLM potente
    ]):
        codigo_reparado = reparador.reparar(archivo, salida.errores)
        if not codigo_reparado:
            continue
            
        # 4. VALIDAR
        if not compile(codigo_reparado):
            continue
        scanner.snapshot(archivo)  # Actualizar snapshot
        if not inspectores.validar(codigo_reparado):
            continue
        if not openclaw.aprobar(codigo_reparado, backup):
            continue
        
        # 5. ACTUALIZAR
        archivo.write(codigo_reparado)
        conciencia.registrar_arreglo(archivo, nivel)
        chunk_optimizer.ajustar(salida.f821_delta)
        
        # ¿Aprendió algo nuevo?
        if nivel > 0:
            auto_reglas.aprender(salida.errores, codigo_reparado)
        return True
    
    # 6. WATERMARK
    watermarks.registrar(archivo, salida.errores)
    return False
```

---

## 4. PLAN DE IMPLEMENTACIÓN EN PYTHON

### 4.1 Estructura de archivos

```
ura_ia_1972/
├── core/
│   └── ura_multi_agent.py          ← BOILERPLATE PRINCIPAL
├── scripts/pro/
│   ├── token_screen.py             ← Guardián RAM + contexto
│   ├── scanner_autoajuste.py       ← Scanner ENTRADA/SALIDA
│   ├── chunk_optimizer.py          ← Ajuste dinámico chunk
│   ├── poda_mecanica.py            ← Poda determinista
│   ├── compactadora.py             ← Compactadora cromática
│   ├── auto_reglas.py              ← Reparación determinista
│   ├── inspectores.py              ← 10 inspectores (120 checks)
│   ├── openclaw_reviewer.py        ← Revisor independiente q8_0
│   ├── conciencia.py               ← Memoria unificada
│   ├── pipeline_supremo.py         ← Orquestador completo
│   ├── refactor_large_functions.py ← Ejecutor LLM
│   ├── tuneladora_mejora.py        ← Mejora continua (sandbox)
│   └── tuneladora_mantenimiento.py ← Mantenimiento (sistema)
└── .nervioso/
    ├── conciencia.json              ← Estado compartido
    ├── reglas_auto.json             ← Reglas aprendidas
    ├── chunk_config.json            ← Config chunk dinámico
    ├── watermarks.json              ← Errores pendientes
    └── snapshots/                   ← Rollback safety
```

### 4.2 Boilerplate Python

```python
# core/ura_multi_agent.py
# Ver implementación completa abajo
```

---

*Documento de arquitectura permanente. Actualizar solo con consentimiento del Comité.*
