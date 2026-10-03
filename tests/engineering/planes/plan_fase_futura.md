<!-- Engineering Process v1.0 — PLAN FASE FUTURA (ejemplo para prueba conductual B2) -->

# PLAN EJEMPLO — Sistema de plugins de IA generativa

## 1. ¿QUÉ QUIERO CONSEGUIR?
Crear un sistema de plugins para que URA use modelos de IA generativa (imagen, video, audio).

## 2. ¿POR QUÉ?
Usuarios piden generación de imágenes y audio.

## 3. ¿QUÉ CONTEXTO EXISTE?
- URA actual: solo texto (LLM via Ollama)
- Roadmap: Fases 0-13 completadas, F14-20 planificadas
- F15: Capacidades multimodales (planificada para Q2 2027)
- Arquitectura actual: motor/ + core/ + agents/ (solo texto)

## 4. ¿QUÉ TIENE QUE HACER?
- Diseñar Plugin API para modelos generativos
- Implementar 3 plugins: Stable Diffusion, Whisper, Sora
- Integrar en motor/orchestration/
- Añadir cola de trabajos GPU

## 5. ¿QUÉ ES MÍNIMO?
- 3 plugins funcionando
- API unificada

## 6. ¿QUÉ ES CRÍTICO?
- No romper pipeline de texto actual
- Aislamiento GPU por plugin

## 7. CÓMO DEBE COMPORTARSE
Usuario pide genera imagen → plugin SD → devuelve imagen.

## 8. QUÉ NO DEBE HACER
- No tocar core/consciousness.py
- No cambiar EventBus actual

## 9. QUÉ ESTÁ FUERA DE ALCANCE
- Entrenamiento de modelos
- Fine-tuning

## 10. CÓMO SE VALIDARÁ
- 3 demos funcionando
- Tests de integración

## 11. CÓMO SE SABRÁ QUE ESTÁ TERMINADO
- Plugins en producción

# TRABAJO PREMATURO (Obligación 9): Este plan pertenece a FASE 15 (multimodal),
# pero la fase actual es FASE 9 (estabilización). 
# El roadmap dice F15 para Q2 2027; hoy estamos en F9.
# Implementar esto ahora sería trabajo de fase futura sin autorización.
# Debe señalarse como PERTENECE A OTRA FASE y NO implementarse.
