# OpenClaw como manos y ojos de URA — Visión estratégica

## Concepto

OpenClaw no es solo automatización de navegador. Es el **observador-aprendiz** que cierra el círculo entre el trabajo manual de Ramón y la automatización futura por URA.

Donde otros sistemas requieren programar cada flujo desde cero, OpenClaw permite que **Ramón enseñe haciendo**: trabaja normalmente mientras OpenClaw observa, documenta, y URA aprende a replicar.

---

## Flujo completo

```
Ramón trabaja manualmente (ej: rellenar formulario de Hacienda)
       ↓
1. OpenClaw OBSERVA la pantalla y registra cada acción (clics, tecleo, navegación)
       ↓
2. Agente registrador (a implementar) documenta el flujo paso a paso
       ↓
3. Agente especialista (Claude API / DeepSeek R1 70B en GX10) genera versión automatizable
       ↓
4. n8n integra el workflow generado en su orquestación
       ↓
5. Sandbox de supervisión valida que la automatización mantiene fidelidad al original
       ↓
6. Si diverge → alarma → Ramón corrige → el ciclo se repite y URA mejora
```

---

## Por qué es la pieza clave del proyecto

- **No requiere programar cada flujo desde cero.** La documentación nace de la observación, no hay "tierra de nadie" entre lo que Ramón hace y lo que URA sabe.
- **Validación automática persona vs URA.** El sandbox compara la ejecución original con la automatizada y alerta si divergen.
- **Ramón enseña haciendo, no escribiendo specs.** Esto elimina la fricción más grande de la automatización: describir el proceso.
- **Ciclo de mejora continua.** Cada corrección de Ramón alimenta el modelo de URA.

---

## Componentes pendientes de diseño

| Componente | Estado | Descripción |
|---|---|---|
| **Agente registrador** | ❌ No existe | Captura lo que OpenClaw observa y lo persiste en formato estructurado (JSON/YAML). |
| **Agente observador-especialista** | ❌ No existe | Convierte observaciones crudas en workflows automatizables (n8n JSON, scripts Python). |
| **Validador de fidelidad** | ❌ No existe | Compara ejecución manual vs ejecución automatizada en sandbox. Calcula score de similitud. |
| **Integración n8n** | ⚠️ Parcial | n8n está instalado en GX10 (:5678) pero no recibe workflows generados automáticamente. |

---

## Dependencias

| Dependencia | Estado |
|---|---|
| GX10 conectado a la red | ✅ Conectado (Tailscale gx10-ts) |
| OpenClaw instalado y autenticado | ✅ Corriendo en Mac (:18789) |
| Permisos de pantalla y accesibilidad en macOS | ⚠️ Requiere configuración manual |
| Modelos grandes en GX10 | ✅ DeepSeek R1 70B, Qwen3 32B, Codestral 22B |
| n8n corriendo en GX10 | ✅ :5678, workflow URA_Auditor configurado |

---

## Riesgos a vigilar

| Riesgo | Mitigación |
|---|---|
| **Privacidad:** OpenClaw verá todo lo que Ramón hace en pantalla | Los datos se procesan localmente. No se envían a APIs externas sin sanitización (`privacy_scrubber.py`). |
| **Sesgo:** si Ramón comete un error, URA aprenderá el error | El sandbox de validación detecta divergencias entre la intención y el resultado. |
| **Sobre-automatización:** no todo flujo debe automatizarse | Ramón decide qué tareas enseña. URA no automatiza por iniciativa propia. |
| **Pérdida de contexto:** OpenClaw ve pantalla, no intención | El agente especialista infiere intención a partir del contexto del sistema (archivos abiertos, historial). |

---

## Enlaces relacionados

- [docs/README_N3.md](README_N3.md) — configuración técnica OpenClaw
- [docs/ciclo_evolutivo.md](ciclo_evolutivo.md) — sistema de sandboxes y aprendizaje
- [docs/MAPEO_MIGRACION.md](MAPEO_MIGRACION.md) — OpenClaw va al GX10
- [docs/ASUS_OPENCLAW_SETUP.md](ASUS_OPENCLAW_SETUP.md) — setup paso a paso

---

*Documento de visión estratégica — 2026-05-12*
