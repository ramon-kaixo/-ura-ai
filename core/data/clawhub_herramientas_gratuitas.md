# Informe de ClawHub: Herramientas gratuitas para URA

**Fecha**: 2026-05-07T19:42
**Autor**: OpenClaw Assistant
**Objetivo**: Seleccionar las 5 skills gratuitas más útiles para URA (asistente de escritorio con agentes cognitivos)

---

## Prioridades de URA
- Búsqueda en Internet
- Filtrado de información
- Descarga de archivos
- Automatización de tareas
- Seguridad

---

## Top 5 Skills Gratuitos Recomendados

### 1. 🧾 summarize

**Función**: Resume o transcribe URLs, YouTube/videos, podcasts, artículos, transcripciones, PDFs y archivos locales.

**Estado**: Requiere instalación (openclaw-bundled, necesita `summarize` via brew)

**Comando de instalación**:
```bash
openclaw skills install summarize
# O manualmente:
brew install summarize
```

**Manual**: https://summarize.sh

**Por qué es útil para URA**:
- Filtrado automático de información de múltiples fuentes
- Resumen de documentos PDF y artículos web
- Transcripción de contenido audiovisual
- Ideal para agentes de investigación y análisis

---

### 2. 🪝 taskflow

**Función**: Coordina tareas multipaso como un trabajo TaskFlow duradero con contexto de propietario, estado, esperas y tareas hijas.

**Estado**: ✓ Ready (openclaw-bundled, sin instalación adicional)

**Comando de instalación**:
```bash
# Ya está disponible, no requiere instalación
openclaw taskflow --help
```

**Manual**: `/opt/homebrew/lib/node_modules/openclaw/skills/taskflow/SKILL.md`

**Por qué es útil para URA**:
- Automatización de workflows complejos
- Orquestación de agentes en cascada
- Gestión de tareas asíncronas con estado persistente
- Ideal para el ciclo de mantenimiento y procesos batch

---

### 3. 🎬 video-frames

**Función**: Extrae frames o clips cortos de videos usando ffmpeg.

**Estado**: ✓ Ready (openclaw-bundled, requiere ffmpeg)

**Comando de instalación**:
```bash
# Ya está disponible si ffmpeg está instalado
openclaw video-frames --help
# Si falta ffmpeg:
brew install ffmpeg
```

**Manual**: https://ffmpeg.org

**Por qué es útil para URA**:
- Procesamiento de contenido multimedia para agentes de visión
- Extracción de frames para análisis de video
- Generación de thumbnails y clips
- Compatibilidad con agentes de galería y vigilancia

---

### 4. 📦 skill-creator

**Función**: Crea, edita, mejora, ordena, revisa, audita o reestructura AgentSkills y archivos SKILL.md.

**Estado**: ✓ Ready (openclaw-bundled, sin instalación adicional)

**Comando de instalación**:
```bash
# Ya está disponible, no requiere instalación
openclaw skill-creator --help
```

**Manual**: `/opt/homebrew/lib/node_modules/openclaw/skills/skill-creator/SKILL.md`

**Por qué es útil para URA**:
- Extensibilidad del sistema: crear nuevos skills personalizados
- Auto-mejora del ecosistema de agentes
- Auditoría de skills existentes
- Ideal para el AgenteDocumentador y mantenimiento del catálogo

---

### 5. ☔ weather

**Función**: Obtiene el clima actual, lluvia, temperatura y pronósticos para ubicaciones o planificación de viajes.

**Estado**: ✓ Ready (openclaw-bundled, requiere curl)

**Comando de instalación**:
```bash
# Ya está disponible (curl viene con macOS)
openclaw weather --help
```

**Manual**: https://wttr.in/:help

**Por qué es útil para URA**:
- Información contextual para planificación de tareas
- Avisos meteorológicos para automatización externa
- Datos ambientales para agentes de hogar/iot
- Útil para agentes de logística y transporte

---

## Skills Adicionales Considerados

### 📱 wacli (WhatsApp)
- **Estado**: Requiere instalación (brew)
- **Función**: Mensajes de terceros y sincronización de historial
- **No seleccionado**: URA ya tiene Telegram bridge, wacli es para historial pasivo

### 💎 obsidian
- **Estado**: Requiere instalación (brew)
- **Función**: Trabajar con vaults de Obsidian
- **No seleccionado**: URA usa su propio sistema de documentación (AgenteDocumentador)

### 🔉 sherpa-onnx-tts
- **Estado**: Requiere descarga de modelos
- **Función**: TTS local offline
- **No seleccionado**: URA ya tiene integración con Ollama para voz si es necesario

### 📄 nano-pdf
- **Estado**: Requiere instalación (uv)
- **Función**: Editar PDFs con lenguaje natural
- **No seleccionado**: summarize cubre lectura de PDFs, edición es menos prioritario

---

## Recomendación de Instalación

Para URA, instalar en este orden:

```bash
# 1. summarize (prioridad alta para filtrado de información)
openclaw skills install summarize

# 2. taskflow, video-frames, skill-creator, weather ya están ready
# Solo verificar dependencias:
brew install ffmpeg  # para video-frames
```

---

## Próximos Pasos

1. Instalar summarize para capacitar a URA con filtrado de información
2. Configurar taskflow para automatizar el ciclo de mantenimiento
3. Integrar video-frames con agentes de visión existentes
4. Usar skill-creator para crear skills personalizados para URA
5. Activar weather para información contextual

---

**Fin del informe**
