# Mapeo de Migración - Mac vs GX10

**Fecha:** 2026-05-11  
**Objetivo:** Definir qué componentes migran a GX10 y cuáles permanecen en el Mac

## Tabla de Migración

| Componente | Destino | Razón |
|-----------|---------|--------|
| Ollama + modelos | GX10 | Necesita 70B+ para modelos grandes |
| Agentes IA pesados (18 agentes) | GX10 | Razonamiento pesado con Ollama |
| n8n | Mac | Orquestación de workflows |
| 8 nodos monitoreo | Mac | Control del Mac local |
| Telegram/Gmail/Slack | Mac | Mensajería y notificaciones |
| PostgreSQL | Mac | Datos pequeños (348K whatsapp_session) |
| Browser agent | Mac | Pantalla del Mac local |
| Dashboard web | Mac | Interfaz del usuario local |
| OpenClaw | GX10 | Necesita potencia GPU |

## Agentes IA Pesados (migran a GX10)

Los siguientes 18 agentes usan Ollama o procesamiento NLP pesado y migrarán a GX10:

1. agente_lenguaje.py - Procesamiento de lenguaje natural con Ollama
2. agente_investigador_ia.py - Investigación con Ollama
3. agente_vision.py - Visión por computadora con Ollama
4. agente_supervisor.py - Supervisión con Ollama
5. agente_vocabulario.py - Vocabulario con Ollama
6. agentes_busqueda.py - Búsqueda con Ollama
7. agente_librarian.py - Bibliotecario con Ollama
8. agente_arquitectura.py - Arquitectura con Ollama
9. registry.py - Registro con Ollama
10. bibliotecario_pasillo.py - Bibliotecario de pasillo con Ollama
11. agente_vocabulario_tecnico.py - Vocabulario técnico con Ollama
12. agente_conversacion.py - Conversación con Ollama
13. agente_modelos.py - Modelos con Ollama
14. agente_reparador.py - Reparación con Ollama
15. agente_sistemas.py - Sistemas con Ollama
16. agente_red.py - Red con Ollama
17. agente_policia_v2.py - Policía v2 con Ollama
18. agente_conciencia.py - Conciencia con NLP

## Componentes que Permanecen en Mac

**Razón principal:** Control local, datos pequeños, o dependen de hardware del Mac

### n8n
- Orquestación de workflows
- Permanece en Mac para control local

### 8 nodos monitoreo
- Control del Mac local
- Monitoreo de recursos del Mac

### Telegram/Gmail/Slack
- Mensajería y notificaciones
- Integraciones locales del Mac

### PostgreSQL
- Datos pequeños (total ~400K)
- No justifica migración a GX10

### Browser agent
- Pantalla del Mac local
- Necesita acceso al display del Mac

### Dashboard web
- Interfaz del usuario local
- Permanece en Mac para acceso local

## Componentes que Migran a GX10

### Ollama + modelos
- mxbai-embed-large:latest (669 MB)
- Necesita potencia para modelos 70B+
- GX10 tiene GPU dedicada

### Agentes IA pesados (18 agentes)
- Usan Ollama para razonamiento
- Procesamiento NLP pesado
- Benefician de GPU del GX10

### OpenClaw
- Necesita potencia GPU
- Cómputo intensivo

## Estrategia de Migración

1. **Fase 1:** Configurar Ollama en GX10
2. **Fase 2:** Migrar agentes IA pesados a GX10
3. **Fase 3:** Configurar OpenClaw en GX10
4. **Fase 4:** Actualizar OLLAMA_HOST a gx10.local:11434
5. **Fase 5:** Verificar funcionamiento
6. **Fase 6:** Eliminar Ollama local del Mac

## Notas

- **Total agentes:** 82 archivos
- **Agentes pesados:** 18 (22%)
- **Agentes ligeros:** 64 (78%) - permanecen en Mac
- **Espacio recuperado estimado:** 15-20GB (Ollama local)
