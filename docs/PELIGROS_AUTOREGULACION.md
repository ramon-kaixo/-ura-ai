# Peligros del sistema autorregulado de URA

## Contexto

URA aspira a un sistema con auditoría permanente, detección de procesos redundantes y simplificación continua. Esto requiere conocer los peligros inherentes al modelo **antes** de que ocurran, no después.

---

## 5 peligros identificados

### 1. Auditor muerto sin avisar

| Aspecto | Detalle |
|---|---|
| **Riesgo** | El `agente_auditor` falla silenciosamente (crash, timeout, except:pass) |
| **Consecuencia** | El sistema sigue "auditándose" pero nadie está mirando. Las automatizaciones se degradan sin que Ramón lo sepa. |
| **Caso real hoy** | `forensic_scribe.py` existe pero tiene 0 importadores. Es exactamente este escenario: el código está, pero no funciona. |
| **Mitigación** | `auditor_del_auditor` — un daemon que cada hora verifica que el auditor sigue respondiendo. Si no responde → alerta Pushover inmediata. |

### 2. Eliminar cosas útiles

| Aspecto | Detalle |
|---|---|
| **Riesgo** | El detector de huérfanos marca como "no usado" algo que SÍ se usa (vía imports dinámicos, strings en registries, config JSON) |
| **Consecuencia** | Pérdida de funcionalidad. Algo que funcionaba deja de funcionar y nadie sabe por qué. |
| **Caso real hoy** | Los 10 generators parecían huérfanos pero el orchestrator los referencia por string en un dict. Si los hubiéramos borrado sin verificar → rotos. |
| **Mitigación** | **Cuarentena de 30 días** en `archive/` antes de borrar definitivamente. Si en 30 días nada falla, se puede eliminar. Si algo falla, se restaura en 1 comando. |

### 3. Tirar complejidad necesaria

| Aspecto | Detalle |
|---|---|
| **Riesgo** | Simplificar fusionando módulos que tienen matices distintos pero el mismo nombre |
| **Consecuencia** | Pérdida de capacidad sutil. El sistema hace "lo mismo" pero peor. |
| **Caso real hoy** | `agente_policia_v2.py` en `agents/` (conversacional con LLM) vs `core/` (validador estructurado con enums). Mismo nombre, distinta responsabilidad. Fusionarlos sería un error. |
| **Mitigación** | `agente_critico` justifica ANTES de simplificar. Si dos módulos hacen cosas distintas → NO se fusionan. Documentar como "falso duplicado". |

### 4. Eliminar redundancia de seguridad

| Aspecto | Detalle |
|---|---|
| **Riesgo** | Tratar como "duplicado inútil" lo que es backup, fallback o redundancia intencional de seguridad |
| **Consecuencia** | Pérdida de resiliencia. El sistema queda sin red de seguridad. |
| **Caso real hoy** | `payment_guardian` tiene 3 niveles (auto, notificar, bloquear). Eliminar el nivel intermedio "por redundante" eliminaría la capacidad de notificar sin bloquear. |
| **Mitigación** | Etiquetar explícitamente: `STUB_INTENCIONAL`, `FALLBACK_INTENCIONAL`, `BACKUP_INTENCIONAL`. El detector de huérfanos respeta estas etiquetas y no las marca. |

### 5. Aprender malos hábitos

| Aspecto | Detalle |
|---|---|
| **Riesgo** | El sistema aprende patrones erróneos de Ramón (un clic de más, un paso innecesario) o de errores no detectados que se repiten |
| **Consecuencia** | Degradación de calidad con el tiempo. URA "aprende" a hacer las cosas mal. |
| **Caso real hoy** | `forensic_scribe.register_root_cause()` existe pero nadie la llama. Si un error se repite 5 veces sin ser corregido, el sistema podría aprenderlo como "comportamiento normal". |
| **Mitigación** | `agente_critico` filtra patrones nuevos antes de incorporarlos al conocimiento permanente. Solo patrones validados explícitamente entran en `semantic_memory`. |

---

## Filosofía

> "Plantar un jardín y podarlo" es mejor que "construir una catedral perfecta de golpe".

Los errores se corrigen solos con el tiempo **SI** hay auditoría confiable. Los peligros son predecibles → si se conocen, se mitigan desde el diseño.

---

## Reglas de implementación

| # | Regla | Estado actual |
|---|---|---|
| 1 | Nada se borra sin cuarentena de 30 días en `archive/` | ✅ Ya se aplica |
| 2 | Nada se simplifica sin pasar por `agente_critico` | ❌ Agente no creado |
| 3 | Toda redundancia intencional debe etiquetarse explícitamente | ⚠️ Parcial (STUBS_INTENCIONALES.md) |
| 4 | El auditor debe tener auditor (cadena de verificación) | ❌ No implementado |
| 5 | Los patrones nuevos requieren validación antes de entrar al conocimiento permanente | ❌ No implementado |

---

*Documento de análisis de riesgos — 2026-05-12*

---

## Principio fundamental: Simplificar ≠ dejar tonto

### Distinción

**Simplificar correctamente:**
- Eliminar duplicados accidentales (copy-paste sin matiz ni intención distinta)
- Quitar capas inútiles que no aportan funcionalidad
- Unificar lo que se separó por error
- Hacer el código entendible sin perder potencia

**Dejar tonto (lo que NO se debe hacer):**
- Quitar capacidad funcional real
- Eliminar redundancia de seguridad (fallbacks, backups, checks dobles)
- Fusionar módulos con matices importantes distintos
- Reducir el número de agentes especialistas porque "parecen iguales"
- Asumir que "más simple" = "mejor" sin verificar

### Ejemplos reales del 2026-05-12

**Correctamente simplificado:**
- ✅ `workflow_engine` archivado — era un duplicado legacy sin diferencias funcionales
- ✅ `URAOrchestrator` archivado — nunca se usó, 0 tareas procesadas
- ✅ LangGraph 50MB fuera — no aportaba nada que central_router no hiciera
- ✅ 16 stubs archivados — eran solo placeholders, no código funcional

**NO se simplificó (decisión correcta verificada):**
- ⛔ `agente_policia_v2` — son dos módulos distintos (conversacional con LLM vs validador estructurado con enums). Fusionarlos habría sido "dejar tonto".
- ⛔ `agente_seguridad` en mobile/ — parecía stub de 35 líneas, era el activo real. El de agents/ era el roto. Archivamos el correcto.
- ⛔ `nodes/utils.py` — parecía huérfano, lo importan 3 módulos de nodes/. Casi lo borramos.
- ⛔ `registry.py` en agents/ vs generators/ — registros distintos (agentes vs generadores). No son duplicados.

### Regla obligatoria antes de simplificar

Hacerse estas 4 preguntas **SIEMPRE** antes de tocar:

1. **¿Por qué existían dos versiones?** ¿Error de copy-paste o decisión de diseño?
2. **¿Qué capacidad se pierde si se fusiona/elimina?** ¿Hay algún método, flag o matiz que desaparece?
3. **¿La diferencia es matiz importante o copy-paste accidental?** ¿Ambos módulos se comportan igual con las mismas entradas?
4. **¿Hay redundancia intencional como seguridad?** ¿Uno es fallback del otro? ¿Es backup por diseño?

**Si la respuesta a cualquiera es "no sé" → NO simplificar. Investigar primero.**

### Filosofía

> "Una cosa es simplificarlo y otra cosa es dejarlo tonto."

La simplificación correcta quita ruido sin quitar capacidad.
La simplificación incorrecta deja un sistema más limpio pero menos capaz.
Un sistema simplificado de más es más frágil que uno con redundancia controlada.
