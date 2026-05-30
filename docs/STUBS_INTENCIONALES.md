# 📦 STUBS INTENCIONALES — NO ARCHIVAR NI BORRAR

## Estado actual

10 archivos plantilla archivados en `archive/stubs_vacios/generators/`. Fueron movidos el 2026-05-11 porque:
- Contienen solo una plantilla vacía (`Expr + Assign + Return`, sin lógica real)
- El orchestrator los referencia por nombre (string mapping), no por import real
- Cero riesgo al moverlos

## Lista de stubs

| Archivo | Líneas | Creado | Qué debería hacer cuando se implemente |
|---|---|---|---|
| `agente_creador_codigo_python.py` | 48 | 2026-05-06 | Generar código Python |
| `agente_creador_codigo_javascript.py` | 34 | 2026-05-06 | Generar código JavaScript |
| `agente_creador_codigo_sql.py` | 38 | 2026-05-06 | Generar consultas SQL |
| `agente_creador_codigo_html.py` | 58 | 2026-05-06 | Generar HTML/CSS |
| `agente_creador_codigo_api.py` | 54 | 2026-05-06 | Generar endpoints API |
| `agente_creador_codigo_microservicios.py` | 56 | 2026-05-06 | Generar microservicios |
| `agente_creador_codigo_ml.py` | 62 | 2026-05-06 | Generar código ML |
| `agente_creador_codigo_data.py` | 53 | 2026-05-06 | Generar pipelines de datos |
| `agente_creador_codigo_devops.py` | 52 | 2026-05-06 | Generar configs DevOps |
| `agente_creador_codigo_seguridad.py` | 60 | 2026-05-06 | Generar código de seguridad |

## Por qué existen

El orchestrator (`core/code_agents/orchestrator.py`, líneas 113-122) mantiene un diccionario de mapeo tipo → archivo:

```python
generator_map = {
    "python": "agente_creador_codigo_python",
    "javascript": "agente_creador_codigo_javascript",
    "sql": "agente_creador_codigo_sql",
    ...
}
```

Son strings de referencia. No se instancian directamente. El orchestrator usa estos nombres para localizar qué generador usar según el tipo de código solicitado.

## Qué NO son

- ❌ No son imports reales (no hay `from X import Y`)
- ❌ No se instancian en runtime
- ❌ No contienen lógica real (plantilla vacía)
- ❌ No son candidatos a borrar — son parte de la arquitectura planeada

## Próximos pasos cuando se implementen

1. Volver a mover cada archivo de `archive/stubs_vacios/generators/` a `core/code_agents/generators/`
2. Implementar `generar()` con lógica real (usando Ollama o plantillas avanzadas)
3. El orchestrator los encontrará automáticamente por nombre

---

*Documento generado durante limpieza de huérfanos — 2026-05-11*

---

## Falsos duplicados — agente_policia_v2.py

Hay dos archivos con el mismo nombre que son módulos distintos:

| Ubicación | Líneas | Rol | Método principal | Importadores |
|---|---|---|---|---|
| `agents/agente_policia_v2.py` | 553 | Conversacional con LLM | `consultar(consulta) -> str` | guardian_openclaw.py |
| `core/agente_policia_v2.py` | 275 | Validador estructurado | `validar(comando) -> dict` | 8 módulos (dashboard, api, tests) |

**NO ARCHIVAR. NO FUSIONAR.** Son implementaciones independientes con responsabilidades diferentes. Mismo nombre, distinto propósito.

A futuro considerar renombrar uno de ellos para evitar confusión: `agente_policia_conversacional.py` vs `agente_policia_validador.py`.

---

## Falsos duplicados resueltos

### agente_seguridad.py — caso invertido (resuelto 2026-05-12)

| Versión | Ubicación | Líneas | Estado |
|---|---|---|---|
| "Stub" | `core/code_agents/mobile/agente_seguridad.py` | 35 | ✅ **ACTIVO** — clase `AgenteSeguridad` con `verificar_seguridad()`. Usado por `orchestrator_mobile.py` (instanciado y llamado en líneas 68-69). |
| "Activo" | `agents/agente_seguridad.py` | 136 | ❌ **ARCHIVADO** — imports rotos (`ejecutor_seguro`, `internet`), aunque esos módulos existen, el código nunca se usaba. Movido a `archive/duplicados/agente_seguridad_legacy_broken.py`. |

**Lección:** No asumir que el archivo más grande o el que está en `agents/` es el activo. Verificar imports reales y uso en runtime.

---

### api_gateway.py — dos intentos fallidos (resuelto 2026-05-12)

| Versión | Ubicación | Estado |
|---|---|---|
| Flask | `archive/duplicados/api_gateway_root_legacy.py` | ❌ Archivado — bug (app.run 2 veces), 0 importadores |
| FastAPI | `gateway/api_gateway.py` | ⚠️ Mantenido como referencia — diseño moderno, 0 importadores |

**Producción real:** nginx en puerto 8091 hace de proxy (config en `/opt/homebrew/etc/nginx/servers/ura_api`).

No son duplicados funcionales — son dos diseños diferentes del mismo concepto. Ninguno está activo en producción. El FastAPI se conserva como código de referencia.

---

## Deuda técnica conocida

### .env en historial Git — RESUELTO 2026-05-12

- **Fecha:** 2026-05-12
- **Problema:** `.env` con tokens (Telegram, Langfuse, Pushover) fue commiteado en 3 commits por error (`git add -A`)
- **Acción tomada:** `git filter-branch` reescribió 344 commits eliminando `.env` del historial completo
- **Verificación:** `git log --all --oneline -- .env` → 0 resultados ✅
- **.gitignore reforzado:** `.env`, `.env.*`, `*.log`, `logs/`, credenciales

**Regla aprendida:** Nunca usar `git add -A`. Siempre `git add <archivos específicos>` y verificar con `git status` antes de commitear.

**Lecciones para el futuro:**
1. El pre-commit hook MEXEM detectó `.env` e impidió commits normales, pero `--no-verify` lo saltó
2. `.gitignore` solo protege archivos NO trackeados — si el archivo ya estaba en git, `.gitignore` no lo detiene
3. Sin remote, el riesgo fue bajo. Con remote, habría requerido rotar TODOS los tokens expuestos
