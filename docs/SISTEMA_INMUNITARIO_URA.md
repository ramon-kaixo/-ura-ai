# Sistema Inmunitario de URA

> **Versión 1.0 — 13 mayo 2026**
> **Estado:** Documentado. Implementación paso a paso desde hoy.

---

## Filosofía base

URA es un organismo vivo. Cada cambio es como un virus que entra:
- Debe identificarse
- Validarse
- Documentarse
- Solo entonces afectar al organismo

**Principios inviolables:**
- NUNCA hay código "en el aire"
- NUNCA dos versiones activas del mismo archivo

---

## Las 3 ubicaciones únicas del código

Todo archivo de URA existe en UNO de estos 3 estados:

| Estado | Ubicación | Significado |
|---|---|---|
| **PRODUCCIÓN** | `~/URA/ura_ia_1972/` (Mac) | Lo que URA usa ahora mismo |
| **SANDBOX** | `~/URA/sandbox/` (GX10) | En pruebas, no afecta a producción |
| **BACKUP** | `~/URA/backup_versiones/` (GX10/Toshiba) | Archivado histórico, solo para rollback |

**Reglas:**
- Un archivo NUNCA está en dos ubicaciones simultáneamente
- NUNCA hay código suelto sin catalogar
- Inventario maestro: `data/inventario_codigo.json` lo sabe todo

---

## Flujo de cualquier cambio de código

```
PASO 1 — Idea/Necesidad
  │  Algo hay que mejorar/arreglar
  ▼
PASO 2 — Copia a sandbox
  │  El archivo se copia de PRODUCCIÓN → SANDBOX
  │  PRODUCCIÓN no se toca
  ▼
PASO 3 — Modificación en sandbox
  │  qwen-coder (u otro) modifica solo en sandbox
  │  agente_sandbox_codigo documenta cada cambio
  ▼
PASO 4 — Verificación
  │  - Tests pasan
  │  - Verificador OK
  │  - 24 horas con 8 pasadas (4 mantenimiento + 4 código)
  ▼
PASO 5 — Aprobación
  │  Si todo OK → cambio se aprueba
  │  Si Ramón requiere → revisión manual
  ▼
PASO 6 — Sustitución atómica
  │  - PRODUCCIÓN actual → BACKUP histórico
  │  - SANDBOX → PRODUCCIÓN
  │  - Carpeta sandbox del archivo se borra
  │  - Inventario actualizado
  ▼
PASO 7 — Cuarentena 30 días
  │  En producción pero vigilado
  │  Si falla en 30 días → rollback automático desde BACKUP
  │  Si pasa 30 días sin fallos → aprobado definitivo
  ▼
  ✅ CAMBIO CONSOLIDADO
```

---

## Agentes responsables

### agente_sandbox_codigo (PENDIENTE crear)
Vigila el sandbox. Su trabajo:
- Recibir copias de archivos para modificar
- Documentar cada movimiento
- Llamar a tests
- Llamar a verificador
- Decidir aprobado/rechazado
- Mover a producción cuando aprobado

### agente_reconocedor (PENDIENTE crear)
Antes de aprobar cualquier cambio:
- Analiza qué hace el cambio
- Detecta puertos abiertos
- Detecta procesos que lanza
- Detecta archivos que toca
- Compara con inventarios aprobados
- Si algo NO documentado → **BLOQUEA**

### sandbox_orchestrator (EXISTE)
- 4 sandboxes: mantenimiento, seguridad, aprendizaje, documentación
- Rotación cada 6h
- Limpieza periódica

### agente_verificador_tareas (EXISTE en GX10)
- Vigila procesos en runtime
- Detecta colgadas
- Alerta por Pushover
- Auto-reanuda auditorías

---

## Inventarios aprobados

```
data/inventario/
├── inventario_codigo.json      ← Todo archivo del proyecto
├── puertos_aprobados.json      ← Puertos que URA puede usar
├── procesos_aprobados.json     ← Procesos que pueden correr
├── apis_externas.json          ← APIs que se pueden llamar
└── archivos_criticos.json      ← Archivos que NO se modifican sin Ramón
```

---

## Sistema de ramales documentados

Cada cambio se registra como un "ramal":

```json
{
  "fecha": "2026-05-13",
  "agente_origen": "qwen-coder",
  "razon": "Arreglar timeout en sandbox",
  "archivo": "core/sandbox.py",
  "version_anterior": "v3.2",
  "version_nueva": "v3.3",
  "lineas_modificadas": [245, 246, 247],
  "afecta_a": ["core/timeout_manager.py"],
  "puertos_afectados": [],
  "procesos_afectados": ["sandbox_runner"],
  "tests_añadidos": 3,
  "estado": "en_sandbox",
  "aprobado_por": ""
}
```

---

## Maletas de contexto

### Maleta común (todos los agentes leen)
```
data/maleta_comun/
├── que_es_ura.md
├── arquitectura.md
├── reglas_oro.md
├── falsos_duplicados.md
├── stubs_intencionales.md
└── glosario.md
```

### Maletas individuales (cada agente la suya)
```
data/maleta_kimi/         ← errores propios, falsos positivos
data/maleta_qwen_coder/   ← fixes aceptados/rechazados
data/maleta_deepseek/     ← decisiones arquitectónicas
```

---

## Calendario operativo

| Frecuencia | Acción | Duración |
|---|---|---|
| **Cada hora (24/7)** | sandbox_orchestrator: quita duplicados, zombis, puertos, código muerto | 10-15 min |
| **Cada 2 horas** | qwen-coder revisa cambios recientes + documentación | 10-15 min |
| **Cada noche (02:00)** | Radiografía completa: hashes de archivos, comparación con día anterior | Variable |
| **Cada lunes (03:00)** | Kimi semanal: análisis de patrones de la semana | 30 min |
| **Cada 15 días (sáb 02:00)** | Kimi quincenal: auditoría profunda completa | 3h |
| **Bajo demanda** | Kimi o DeepSeek si hay emergencia | Variable |

---

## Pre-commit hook (Git)

Antes de aceptar cualquier commit:

1. Verifica que el archivo PASÓ por sandbox
2. Verifica que está en el inventario
3. Verifica que hay ramal documentado
4. Verifica que tests pasan
5. Verifica que NO hay puertos sin documentar
6. Si todo OK → permite commit
7. Si algo falla → **BLOQUEA** + reporta qué documentar

---

## Sistema de aprobación

| Tipo | Aprobación |
|---|---|
| **Manual** (Ramón) | Cambios críticos, core/, puertos nuevos |
| **Automática** (cuarentena 30d) | Cambios menores, fixes catalogados, mejoras documentadas |

---

## Detección de fallos persistentes

Si un error se repite 3+ veces en 24h:
- Sistema lo marca "persistente"
- Activa revisión urgente
- Kimi audita el archivo específico
- Genera fix + tests
- Documenta en `bugs_conocidos.jsonl`

---

## Lo que NUNCA debe pasar

- ❌ Modificar producción directo (sin pasar por sandbox)
- ❌ Dos versiones activas del mismo archivo (limpio.sh + robusto.sh)
- ❌ Archivo sin catalogar en inventario
- ❌ Cambio sin ramal documentado
- ❌ Commit sin pasar pre-commit hook
- ❌ Aprobar sin verificador OK

---

## Estado actual

**PRESENTE:**
- ✅ sandbox_orchestrator.py (4 sandboxes con rotación 6h)
- ✅ agente_verificador_tareas (GX10, activo)
- ✅ forensic_scribe (conectado a central_router)
- ✅ timeout_manager.py (creado)
- ✅ thread_cleaner.py (existe)
- ✅ network_audit (existe)

**AUSENTE:**
- ❌ agente_sandbox_codigo (hay que crear)
- ❌ agente_reconocedor (hay que crear)
- ❌ Inventario maestro (hay que crear)
- ❌ Pre-commit hook (hay que crear)
- ❌ Cron horario para sandbox (hay que configurar)
- ❌ Maletas (hay que crear)

---

## Plan de implementación inmediata (hoy)

| Paso | Acción | Estado |
|---|---|---|
| 1 | Documento creado (este archivo) | ✅ |
| 2 | Estructura de carpetas sandbox + inventario + ramales | Pendiente |
| 3 | Inventario inicial del código actual | Pendiente |
| 4 | agente_sandbox_codigo (versión mínima) | Pendiente |
| 5 | Regla manual activa: OpenCode no toca core/ sin avisar | Pendiente |
| 6 | Pre-commit hook básico | Pendiente |

**Próximas sesiones:**
- agente_reconocedor completo
- Inventarios de puertos/procesos
- Cron horario sandbox_orchestrator
- Maletas de contexto
