# Arquitectura Autónoma de URA

## Principios Fundamentales

URA opera como un sistema autónomo que puede gestionar su propia arquitectura, integraciones y herramientas sin dependencia humana constante. Este documento define las reglas y principios que guían esta autonomía.

## Lo que NO se debe hacer

### Reglas Obligatorias

#### REGLA OBLIGATORIA — Incorporación de herramientas externas

Ninguna herramienta o servicio externo puede entrar en producción sin cumplir estos 4 requisitos en orden:

1. **Sandbox 1 — Instalación y conexión básica verificada**
   - Instalar la herramienta/servicio en entorno aislado
   - Verificar que se pueda conectar y ejecutar comandos básicos
   - Documentar los pasos de instalación y configuración
   - Probar que la herramienta responde correctamente

2. **Sandbox 2 — Integración con URA probada**
   - Integrar la herramienta con el código de URA
   - Probar la comunicación bidirecional
   - Verificar que URA puede invocar la herramienta
   - Probar casos de uso básicos y flujos normales

3. **Sandbox 3 — Pruebas de estrés y casos de fallo**
   - Someter la integración a pruebas de carga
   - Probar casos de fallo y recuperación
   - Verificar comportamiento ante errores
   - Documentar límites y puntos de ruptura

4. **Sandbox 4 — Manual en docs/ completo y revisado**
   - Crear manual completo en `docs/` explicando:
     - Cómo está configurada la herramienta en URA
     - Cómo usarla desde el código de URA
     - Endpoints/API relevantes
     - Qué hacer cuando falla
     - Casos de uso y ejemplos
   - Revisar que el manual sea claro y completo
   - **Sin manual en docs/, la herramienta no se activa**

**Ejemplos de herramientas que deben seguir este proceso:**

- n8n (workflow automation)
- Ollama (AI models)
- Redis (caching)
- PostgreSQL (database)
- Prometheus (metrics)
- Grafana (dashboards)
- Telegram (notifications)
- Slack (notifications)

**Violación de esta regla:**

- Si se intenta activar una herramienta sin manual en docs/, el sistema debe bloquear la activación
- URA debe verificar la existencia del manual antes de permitir el uso de la herramienta
- El manual debe ser revisado por URA para asegurar que cubre todos los aspectos necesarios
