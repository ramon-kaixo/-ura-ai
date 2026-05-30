# Modelo de gerencia — URA como negocio

## Analogía

```
URA       = empresa
Ramón     = dueño
OpenClaw  = gerente (mano derecha)
Modelos grandes = consultores externos
Agentes URA     = trabajadores especializados
n8n       = fábrica automatizada
Auditor   = supervisor permanente
```

---

## Vías de comunicación

### Vía principal (normal)

```
Ramón → URA → URA decide → OpenClaw ejecuta si hace falta
```

El dueño habla con la empresa. La empresa decide si delegar al gerente. El gerente ejecuta. Los consultores asesoran si se necesita conocimiento experto.

### Vía directa (botón especial)

```
Ramón → OpenClaw directo
```

**CONDICIÓN OBLIGATORIA:** URA registra TODO. OpenClaw nunca actúa sin que URA lo sepa. `forensic_scribe` recibe cada orden y cada resultado, venga de donde venga.

---

## Reglas del gerente (OpenClaw)

### Regla 1: Justificar antes de actuar

Antes de proponer cualquier acción:

1. **Inventariar herramientas existentes.** ¿Qué agentes, scripts, flujos n8n hay ya?
2. **Evaluar si sirven para la tarea.** ¿Puedo resolver esto con lo que ya tengo?
3. **Si no sirven → justificar por qué.** "No existe agente para X porque..."
4. **Solo entonces proponer** modificación, creación o adquisición.
5. **La justificación queda registrada** en `forensic_scribe` para trazabilidad.

### Regla 2: El crítico

`agente_critico` (pendiente de crear) cuestiona cada propuesta:

- ¿Por qué esta decisión y no otra?
- ¿Se han revisado TODAS las opciones existentes?
- ¿Las herramientas pedidas están justificadas?
- ¿Hay una alternativa más simple?

Sin pasar el crítico, OpenClaw no ejecuta.

### Regla 3: El auditor

`agente_auditor` (pendiente de implementar) supervisa automatizaciones:

- Las automatizaciones siguen funcionando como se aprobaron
- Producen el mismo resultado que cuando se validaron
- No hay desviación de calidad ni de comportamiento
- Si detecta divergencia → alerta a Ramón

---

## Componentes pendientes

| Pieza | Función | Estado |
|---|---|---|
| Bridge URA ↔ OpenClaw | Comunicación bidireccional con registro automático | ❌ Pendiente |
| `agente_critico` | Justifica decisiones antes de actuar, cuestiona propuestas | ❌ Pendiente |
| `agente_auditor` | Supervisa automatizaciones, detecta desviaciones | ⚠️ Stub vacío |

---

## Interfaz en OpenWebUI

Dos botones de envío:

1. **"URA"** — vía normal. URA clasifica, asigna agente, decide si usar OpenClaw.
2. **"OpenClaw directo"** — Ramón habla directamente con OpenClaw, pero con **auditoría obligatoria** registrada en URA (`forensic_scribe`). OpenClaw ve la pantalla, ejecuta, y URA lo anota TODO.

---

## Por qué este modelo evita la tierra de nadie

Cada acción lleva 5 capas de registro:

1. **Justificación** (por qué se hace)
2. **Inventario de alternativas** (qué se descartó y por qué)
3. **Registro automático** (`forensic_scribe`)
4. **Crítica previa** (`agente_critico`)
5. **Auditoría posterior** (`agente_auditor`)

Imposible que algo "se haga sin saber por qué". Cada decisión tiene trazabilidad completa.

---

## Filosofía

> "Como gerente bueno: no compra máquinas nuevas si las viejas funcionan."

**Justificación obligatoria > acción impulsiva.** OpenClaw no puede proponer instalar nada sin antes demostrar que lo que ya existe no sirve.

---

*Documento de filosofía de gerencia — 2026-05-12*
