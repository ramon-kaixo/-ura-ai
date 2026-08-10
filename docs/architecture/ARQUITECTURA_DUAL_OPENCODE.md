<!-- PLAN_TEMPLATE v1.0 — Engineering Process -->

# PLAN — Arquitectura Dual OpenCode (Web + Escritorio) — Documentación de lo existente

- **Estado**: IMPLEMENTADO Y VERIFICADO (2026-08-09) — documento descriptivo de lo que ya está en producción
- **Versión**: 1.0
- **Autor**: TERM (OpenCode Web), con validación de Ramón
- **Motivo del documento**: describir formalmente la arquitectura dual ya montada (que el plan propuesto por otra IA describía como futura — aquí está documentada tal como es, con los roles correctos según la regla principal de URA)

---

## 1. ¿QUÉ QUIERO CONSEGUIR? (Objetivo)

Tener **dos interfaces de OpenCode trabajando en paralelo** sobre el mismo proyecto, con redundancia (si una cae, la otra sigue), Git como origen de verdad único, y trazabilidad UDO completa:

- **Ventana 1 — OpenCode Web** (ASUS): agente de trabajo principal + interfaz web de visualización.
- **Ventana 2 — OpenCode Escritorio** (Mac): segunda interfaz con cerebro local Qwen 32B, para revisar/consultar/corregir en paralelo.

## 2. ¿POR QUÉ? (Intención / Problema)

| Problema | Consecuencia | Solución implementada |
|----------|--------------|------------------------|
| Un solo punto de fallo | Si la web cae, todo se detiene | El escritorio (Mac) trabaja con su propio cerebro local (Qwen 32B) sin depender de la web |
| Dificultad para distinguir ventanas | Confusión sobre quién es quién | Cerebros distintos (DeepSeek vs Qwen 32B) + comando `ura-doble quien` |
| Sin trazabilidad entre agentes | No se sabía quién hizo qué | UDO: TASK-ID, commits `[WEB]`/`[TERM]`, gate, verify |
| Desincronización de código | Mac y ASUS con versiones distintas | Git: remote `asus` + `ura-doble sync` |

## 3. ¿QUÉ CONTEXTO EXISTE? (Estado real verificado)

| Componente | Dónde | Estado |
|-----------|-------|--------|
| OpenCode 1.17.7 (binario) | ASUS: `~/.opencode/bin/opencode` | ✅ |
| Servidor web (Ventana 1) | ASUS: `opencode web :8081` (PID activo) | ✅ HTTP 200 |
| Proyecto Ventana 1 | ASUS: `/home/ramon/URA/ura_ia_1972` | ✅ fuente de verdad |
| Cerebro Ventana 1 | DeepSeek V4 Flash (sesión actual) | ✅ |
| OpenCode 1.17.7 (binario) | Mac: `~/.opencode/bin/opencode` | ✅ |
| Servidor web local (Ventana 2) | Mac: `opencode web :8091` (PID activo) | ✅ HTTP 200 |
| Proyecto Ventana 2 | Mac: `/Users/ramonesnaola/URA/ura_ia_1972` | ✅ sincronizado (HEAD `f2b2caa4`) |
| Cerebro Ventana 2 | Qwen 32B local (Ollama del Mac) — únicos providers: `['ollama']` | ✅ |
| Sincronización | Mac → ASUS: remote git `asus` + `ura-doble sync` | ✅ |
| Puente de revisión | `~/.opencode/bin/ura-doble` (instalado en Mac) | ✅ |
| Suites | UDO 35/35 · Engineering 13/13 · pytest 5942 passed | ✅ |
| UDO | Tareas, reservas, gate, verify, review-pending | ✅ v5 |

## 4. ¿QUÉ TIENE QUE HACER? (Arquitectura real)

```
                    TU MAC (Mini-de-RAMON)
┌─────────────────────────────────────────────────────┐
│  VENTANA 2 — OpenCode Escritorio                    │
│  🧠 Qwen 32B (Ollama local del Mac)                 │
│  http://127.0.0.1:8091                              │
│  Proyecto: ~/URA/ura_ia_1972                        │
│  Rol: revisar / consultar / corregir en paralelo    │
└──────────────┬──────────────────────────────────────┘
               │ git remote "asus" + ura-doble sync
               ▼
┌─────────────────────────────────────────────────────┐
│  ASUS GX10 (fuente de verdad)                       │
│  VENTANA 1 — OpenCode Web                           │
│  🧠 DeepSeek V4 Flash                               │
│  http://10.164.1.99:8081                            │
│  Proyecto: /home/ramon/URA/ura_ia_1972              │
│  Rol: agente de trabajo principal + visualización   │
└─────────────────────────────────────────────────────┘
```

### Piezas instaladas (todas verificadas hoy)

| Pieza | Función | Evidencia |
|-------|---------|-----------|
| `opencode web :8081` (ASUS) | Servidor web principal | systemd `opencode.service`, activo |
| `opencode web :8091` (Mac) | Servidor web local del escritorio | proceso activo, HTTP 200 |
| `ura-doble` (Mac) | Puente: sync + status + list + verify + quien + revisar | instalado en `~/.opencode/bin/` |
| remote git `asus` (Mac) | Sincronización Mac ↔ ASUS | `git remote -v` → asus |
| UDO (`ura-udo`) | Tareas, reservas, gate, verificación | suite 35/35 |
| `ura-opencode` | Envío de trabajo a la Web | script en scripts/pro/ |

## 5. ¿QUÉ ES MÍNIMO? (Mínimos obligatorios)

1. La Ventana 2 funciona sin depender de la Ventana 1 (cerebro local Qwen 32B + repo local). ✅
2. La Ventana 1 sigue siendo la fuente de verdad del código (AGENTS.md: "SIEMPRE TRABAJAR EN ASUS"). ✅
3. Git mantiene ambos repos sincronizados (`ura-doble sync`). ✅
4. Todo cambio se identifica con TASK-ID en el commit. ✅ (UDO)
5. `ura-doble quien` permite saber en qué ventana se está. ✅

## 6. ¿QUÉ ES CRÍTICO? (Puntos críticos / Invariantes)

- **NO invertir los roles**: ASUS es el agente de trabajo principal y fuente de verdad (regla principal de URA). El Mac es la ventana de escritorio/paralela — NO el servidor principal.
- **NO migrar a OpenHands ni a otra herramienta** (Opción B descartada): UDO, metodología Plan 0, mutmut, gate y suites están construidos sobre OpenCode — migrar tira días de trabajo verificable.
- Git es el origen de verdad único; la web NO es el origen.
- La configuración del Mac solo expone Ollama/Qwen 32B (`disabled_providers`), para que la Ventana 2 no confunda con mimo/deepseek.
- Trazabilidad: TASK-ID → commits → verify → DONE con gate.

## 7. ¿CÓMO DEBE COMPORTARSE? (Comportamiento esperado)

- Abrir `http://10.164.1.99:8081` → OpenCode Web (DeepSeek), proyecto ASUS.
- Abrir `http://127.0.0.1:8091` (en el Mac) → OpenCode Escritorio (Qwen 32B), proyecto local sincronizado.
- `ura-doble revisar` en el Mac → sincroniza + lista tareas a revisar.
- Si la web de ASUS cae → la Ventana 2 sigue funcionando (cerebro local).
- Si el Mac cae → la Ventana 1 sigue (todo el trabajo está en ASUS).

## 8. ¿QUÉ NO DEBE HACER? (NO HACER)

- NO hacer de la Ventana 2 (Mac) el agente de trabajo principal.
- NO migrar a OpenHands / AgentBox / amux (descartado — reutilizar lo existente).
- NO borrar ni renombrar `ura-udo`, `ura-doble`, `ura-opencode` ni las suites.
- NO añadir el provider `opencode` (mimo) ni `deepseek` a la config de la Ventana 2 (ya desactivados).
- NO crear infraestructura nueva (BD, paneles, colas) — UDO ya cubre la coordinación.
- NO tocar el `opencode.service` de ASUS sin reiniciar y verificar después.

## 9. ¿QUÉ ESTÁ FUERA DE ALCANCE?

- Migración a otra herramienta (OpenHands, etc.).
- Canal de voz/Kimi como parte de la arquitectura (puede ser canal humano externo, no pieza del sistema).
- Cambiar el cerebro de la Ventana 1 (DeepSeek — es la que el usuario usa).
- Automatización de la sincronización en tiempo real (la sync es manual con `ura-doble sync`; git fetch+merge bajo demanda).

## 10. ¿CÓMO SE VALIDARÁ? (Validación — ya ejecutada)

| Check | Resultado |
|-------|-----------|
| `ura-doble quien` (Mac) | ✅ Identifica ambas ventanas (máquina, proyecto, cerebro) |
| `ura-doble sync` (Mac) | ✅ "Repo del Mac al día con ASUS" |
| `ura-doble status/list/verify` (Mac) | ✅ Estado UDO real vía SSH |
| HTTP :8081 (ASUS) | ✅ 200 |
| HTTP :8091 (Mac) | ✅ 200 |
| Providers Ventana 2 | ✅ solo `['ollama']` |
| Suites UDO/Engineering/pytest | ✅ 35/35 · 13/13 · 5942 |

## 11. ¿CÓMO SE SABRÁ QUE ESTÁ TERMINADO? (Criterios de cierre)

1. Ambas ventanas visibles y operativas (verificadas hoy).
2. `ura-doble` funcional en el Mac con sus 6 subcomandos.
3. Ventana 2 con Qwen 32B exclusivo (sin mimo/deepseek).
4. Repo del Mac sincronizado con ASUS (`f2b2caa4`).
5. Este documento refleja la realidad verificada (no propuestas).

---

*Documento descriptivo de la arquitectura ya implementada. No introduce cambios — registra el estado real verificado el 2026-08-09.*
