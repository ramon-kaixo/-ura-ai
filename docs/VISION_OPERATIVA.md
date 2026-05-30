# Visión operativa de URA — Cómo va a funcionar de verdad

## Cadena de mando

```
Ramón → OpenWebUI → URA → OpenClaw → Modelos grandes en GX10
```

Cada nivel solo habla con el inmediato superior o inferior. Ramón no le da órdenes directamente a OpenClaw. URA no habla directamente con los modelos del GX10.

---

## Reglas principales

1. **Ramón habla SOLO con URA** (vía OpenWebUI). Es la única interfaz de entrada de tareas.
2. **URA decide cuándo usar OpenClaw.** Si la tarea requiere ejecutar acciones reales (click, navegar, escribir), URA delega en OpenClaw. Si es solo conversación, URA responde directamente.
3. **OpenClaw es las manos y los ojos de URA.** No toma decisiones. Ejecuta lo que URA le pide y devuelve el resultado.
4. **URA registra TODO lo que OpenClaw hace.** Cada acción de OpenClaw queda en `forensic_scribe`. Cada resultado en `observability`. Trazabilidad completa.
5. **OpenClaw busca soluciones en Internet si se atasca.** Si una tarea falla, OpenClaw puede buscar en Google/DuckDuckGo antes de rendirse.
6. **forensic_scribe escribe el motivo y resultado de cada acción.** Lenguaje natural, no JSON ilegible. "Ramón pidió X → URA asignó agente Y → OpenClaw hizo Z → resultado: éxito/fallo por tal motivo".

---

## Flujo de una orden

```
1. Ramón escribe "crea factura para el cliente López, 150€" en OpenWebUI
       ↓
2. URA recibe, clasifica (agente_facturas), asigna
       ↓
3. URA invoca OpenClaw: "abre el programa de facturación, rellena estos datos"
       ↓
4. OpenClaw ejecuta:
   - abre la app de facturación
   - navega al formulario
   - rellena los campos
   - si falla → busca en Internet cómo hacerlo → reintenta
       ↓
5. URA registra todo:
   - forensic_scribe: "URA pidió a OpenClaw crear factura para López por 150€. OpenClaw abrió FacturaScripts, rellenó formulario, guardó PDF."
   - observability: latencia=4.3s, agente=facturas, estado=éxito
       ↓
6. URA responde a Ramón: "✅ Factura creada para López (150€). PDF guardado en ~/facturas/"
       ↓
7. Si la tarea tarda > 5 minutos → URA avisa por Pushover: "La factura de López sigue en proceso..."
```

---

## Bucle de mejora

```
1. forensic_scribe registra patrones de tareas repetidas
       ↓
2. Sandbox de aprendizaje detecta: "esto ya se ha hecho 5 veces igual"
       ↓
3. URA propone a Ramón: "¿Quieres automatizar la facturación mensual con n8n?"
       ↓
4. Ramón acepta → n8n recibe el workflow generado
       ↓
5. n8n ejecuta el flujo sin intervención de Ramón
       ↓
6. URA supervisa que la automatización sigue funcionando
   - Si n8n falla → URA alerta a Ramón
   - Si el formato de factura cambia → URA detecta divergencia y pide revisión
```

---

## Ventajas vs estado actual

| Estado actual | Estado objetivo |
|---|---|
| 3 caminos paralelos (central_router, workflow_engine, Telegram) | 1 sola entrada: OpenWebUI → central_router |
| OpenClaw es un gateway pasivo | OpenClaw ejecuta tareas reales y busca soluciones |
| forensic_scribe huérfano (0 importadores) | forensic_scribe conectado a cada acción |
| Sin trazabilidad de tareas | Cada tarea registrada con origen, motivo, resultado |
| Sin alertas de fallos | Pushover alerta si algo va mal |
| Pagos >100€ congelados sin aprobación remota | Telegram bot permite aprobar/rechazar desde el móvil |

---

## Dependencias

| Dependencia | Estado |
|---|---|
| GX10 conectado a red | ✅ Conectado (Tailscale gx10-ts) |
| Modelos grandes descargados | ✅ qwen3:32b, codestral:22b, deepseek-r1:70b, qwen2.5-coder:32b |
| OpenWebUI instalado | ✅ Puerto :3001 (corriendo) |
| central_router como punto único | ⚠️ Pendiente (Fase A del plan) |
| OpenClaw integrado con URA | ❌ Pendiente |
| forensic_scribe conectado | ❌ Pendiente |
| Sistema de timeouts | ❌ Pendiente |
| Agente verificador | ❌ Pendiente |
| Aprobación remota de pagos | ❌ Pendiente |

---

## Plan secuencial

### Semana 1 — Fundación
- [x] GX10 en red con Tailscale
- [x] Modelos grandes descargados (qwen3, codestral, deepseek, qwen2.5-coder)
- [x] OpenWebUI funcionando en Mac (:3001)
- [ ] central_router como ÚNICO punto de entrada (Fase A)
- [ ] Revisión de código completo con deepseek-r1:70b

### Semana 2 — Trazabilidad
- [ ] forensic_scribe conectado a central_router
- [ ] observability ampliado a todo el pipeline
- [ ] Sistema de timeouts implementado
- [ ] Primeras órdenes reales con trazabilidad completa

### Semana 3+ — Autonomía
- [ ] Carga de bibliotecas y documentos
- [ ] Automatización de tareas repetitivas con n8n
- [ ] Agente verificador corriendo como daemon
- [ ] Mejora continua basada en forensic_scribe

---

*Documento de visión operativa — hacia dónde va URA.*
