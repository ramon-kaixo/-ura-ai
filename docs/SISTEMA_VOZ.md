# Sistema de Voz para URA

> **Fecha:** 2026-05-12
> **Estado:** Diseño completo, no implementado

---

## 1. Objetivo

Que Ramón pueda hablar con URA por voz con:
- Máxima claridad de captura
- Mínima latencia
- Auto-adaptación a su voz (Navarra, euskera, vocabulario propio)
- Independencia del hardware (altavoz Bluetooth, micrófono cualquiera)

---

## 2. Problema actual

| Problema | Impacto |
|---|---|
| Whisper genérico transcribe mal palabras propias | "URA" → "hura", "OpenClaw" → "open clon" |
| A veces escribe cosa completamente distinta | Transcripción inutilizable |
| No distingue acento del usuario | Confunde español/euskera |
| No tiene vocabulario propio del proyecto | Términos técnicos no reconocidos |

---

## 3. Arquitectura propuesta

```
Ramón habla ──→ [Micrófono Mac] ──→ [VAD + Wake-word] ──→ [Whisper GX10] ──→ [texto]
                                                                                    │
                                                                                    ▼
Ramón escucha ←── [Altavoz Mac] ←── [Piper TTS Mac] ←──────────────── [URA responde]
```

### 3.1 Captura de voz (Mac)
- **CoreAudio** detecta automáticamente dispositivos
- Script `auto_audio_config.sh`:
  - Detecta micrófono activo
  - Ajusta nivel automáticamente
  - Activa cancelación de eco si hay altavoz BT
  - Activa filtro de ruido de fondo
  - Guarda config en `~/.ura/audio_profile.json`

### 3.2 Transcripción (GX10)
- **Modelo:** Whisper-large-v3 (mejor precisión)
- **Idioma forzado:** español
- **Initial prompt** con vocabulario propio:
  ```
  URA, OpenClaw, Kimi-Dev, Eneko, Tailscale, GX10, ASUS, Ollama,
  Langfuse, central_router, forensic_scribe, OpenCode, OpenWebUI,
  Docker, n8n, PM2, PayPal, Bizum, IZEN, Hacienda, factura,
  agente_, sandbox_, Navarra, Pamplona, pintxos, euskera
  ```
- **Temperature baja** (0.0) para menos invención

### 3.3 Adaptación a Ramón
- Cada transcripción exitosa → `data/voz/transcripciones_ok.jsonl`
- Cada corrección de Ramón → `data/voz/correcciones.jsonl`
- Periódicamente (mensual) se genera un **"vocabulary boost"** personalizado
- Whisper usa este vocabulario en cada llamada futura

### 3.4 Síntesis de voz (Mac, local)
- **Modelo:** Piper TTS
- Voces disponibles:
  - `es_ES-davefx-medium` — voz masculina natural
  - `es_ES-mls_9972-low` — voz masculina ligera
  - `es_ES-carlfm-x_low` — voz masculina ultra-ligera
- **Latencia:** < 200ms
- Voz configurable por el usuario

### 3.5 Detección de actividad de voz (VAD)
- Solo se activa la grabación si detecta voz
- Evita procesar silencios (ahorra CPU y coste de transcripción)
- **Motor:** silero-vad (ONNX, ligero)

### 3.6 Activación por palabra (Wake Word)
- **Triggers:** "Hey URA" o "Laia"
- **Modelo:** Porcupine (Picovoice) u OpenWakeWord
- Siempre escuchando pero solo envía a Whisper si oye el trigger
- Bajo consumo (< 5% CPU en idle)

---

## 4. Hardware soportado

| Dispositivo | Tipo | Detección |
|---|---|---|
| Altavoces | Bluetooth, USB, jack 3.5mm, integrado | Auto |
| Micrófonos | Interno Mac, USB, BT con micro, lavalier | Auto |
| Auriculares | Cualquiera con micro | Auto |

Auto-detección al arrancar el sistema vía `auto_audio_config.sh`.

---

## 5. Plan de implementación

### Fase 1 — Whisper-large mejorado (próxima sesión)
1. Instalar whisper-large-v3 en GX10
2. Crear endpoint REST de transcripción (`POST /transcribe`)
3. Pasar vocabulario propio en cada llamada vía `initial_prompt`
4. Medir precisión vs Whisper genérico actual

### Fase 2 — Auto-config audio Mac
1. Script `auto_audio_config.sh`:
   - Detección de dispositivos (`system_profiler SPAudioDataType`)
   - Ajuste de nivel automático (`osascript -e "set volume input volume 75"`)
   - Cancelación de eco (CoreAudio `kAudioUnitSubType_VoiceProcessingIO`)
   - Filtro de ruido (`AEC`, `AGC` en macOS)

### Fase 3 — Aprendizaje continuo
1. Logging de transcripciones en `data/voz/`
2. Sistema de corrección manual (Ramón corrige → se guarda)
3. Generación mensual de vocabulary boost
4. Métricas de precisión por sesión

### Fase 4 — Activación por voz
1. Instalar Porcupine wake-word engine
2. Configurar "Hey URA" y "Laia" como triggers
3. Integrar VAD (silero-vad) para ahorrar procesamiento
4. Pipeline completo: wake-word → VAD → grabación → transcripción → respuesta

### Fase 5 — Síntesis TTS local
1. Instalar Piper TTS en Mac (`brew install piper`)
2. Descargar voces españolas
3. Integrar con URA para leer respuestas en voz
4. Latencia < 200ms

---

## 6. Estado actual

| Componente | Estado |
|---|---|
| Sistema de voz integrado | ❌ No existe |
| Whisper (genérico) | ⚠️ Instalado en Mac (openai-whisper) |
| Whisper-large-v3 en GX10 | ❌ No descargado |
| Piper TTS | ❌ No instalado |
| Auto-config audio | ❌ No implementado |
| Vocabulario propio | ❌ No configurado |
| Wake-word | ❌ No implementado |
| VAD | ❌ No implementado |

---

## 7. Próximos pasos

1. **Fase 1 ahora:** Whisper-large-v3 en GX10 con vocabulario propio
2. **Fase 2 después:** Auto-config audio en Mac
3. **Fases 3-5:** Según necesidad

---

## 8. Comandos rápidos (futuro)

```bash
# Probar captura de audio
./scripts/auto_audio_config.sh

# Transcribir audio vía GX10
curl -X POST http://gx10-ts:9090/transcribe -F "audio=@grabacion.wav"

# Síntesis de voz local
echo "Hola Ramón" | piper --model es_ES-davefx-medium --output_file respuesta.wav
```
