# Sistema de voz multiusuario — Fase 4 (futura)

> **Fecha:** 2026-05-13
> **Estado:** Documentado, no implementado
> **Depende de:** Fase 1 (aceptar/rechazar), Fase 2 (comparador), Fase 3 (análisis mensual)

---

## 1. Propuesta

Que URA reconozca quién está hablando y adapte transcripción + correcciones a cada persona individualmente. Ramón, Eneko, y cualquier otro usuario futuro.

---

## 2. Componentes técnicos

### 2.1 Identificación de hablante (speaker diarization)

- **Librería:** `pyannote.audio` (modelos preentrenados en HuggingFace)
- **Requisito:** ~30-60 segundos de muestra inicial por persona
- **Modelo:** `pyannote/speaker-diarization-3.1`
- **Pipeline:** `pyannote/embedding` → genera vector de huella acústica por hablante

### 2.2 Estructura de perfiles

```
data/voz/perfiles/
├── ramon.json
├── eneko.json
└── generico.json      ← fallback para desconocidos
```

**Formato del perfil (`ramon.json`):**
```json
{
  "id": "ramon",
  "nombre": "Ramón",
  "voice_embedding": [0.123, -0.456, ...],
  "vocabulario": ["URA", "OpenClaw", "GX10", "Eneko"],
  "correcciones": {
    "open claw": "OpenClaw",
    "central router": "central_router"
  },
  "patrones": {
    "velocidad_palabras_min": 200,
    "tono_medio_hz": 130,
    "acento": "navarra",
    "idioma_principal": "es"
  },
  "estadisticas": {
    "sesiones_totales": 0,
    "tasa_aceptacion": 0.0,
    "correcciones_acumuladas": 0,
    "creado": "2026-05-13"
  }
}
```

### 2.3 Flujo de transcripción multiusuario

```
audio.wav
    │
    ▼
[pyannote.audio] → identifica hablante(s)
    │
    ├── Hablante conocido → cargar perfil.json
    │       │
    │       ├── Whisper con initial_prompt del perfil
    │       ├── Correcciones específicas del perfil
    │       └── Guardar en historial del perfil
    │
    └── Hablante desconocido → perfil genérico
            │
            └── Preguntar "¿quién eres?"
```

### 2.4 Aprendizaje independiente por perfil

Cada perfil aprende de SU historial sin mezclar:
- Sus rechazos/aceptaciones
- Sus correcciones manuales (vía `/feedback`)
- Sus patrones detectados (velocidad, tono)

Los datos de Ramón no contaminan los de Eneko, y viceversa.

---

## 3. Onboarding de nuevo usuario

1. Persona dice: "Mi nombre es X y voy a usar URA"
2. Sistema detecta voz desconocida → genera embedding
3. Pregunta: "¿Quién eres? [opciones: crear nuevo / soy Y]"
4. Si nuevo → graba 60 segundos de muestra guiada
5. Crea `perfil_X.json` con embedding + vocabulario base
6. A partir de ahora, X queda identificado automáticamente

---

## 4. Beneficios

- Cada usuario tiene precisión optimizada para su voz
- Vocabulario familiar/laboral por persona
- No interfiere el aprendizaje entre usuarios
- Detecta cuando hablan varias personas en una grabación
- Las correcciones de Ramón no corrompen las de Eneko

---

## 5. Requisitos previos

| Fase | Descripción | Estado |
|---|---|---|
| Fase 1 | Sistema de aceptar/rechazar transcripciones | ✅ Implementado |
| Fase 2 | Comparador de intentos (elegir mejor) | ❌ Pendiente |
| Fase 3 | Análisis mensual de transcripciones | ❌ Pendiente |
| Fase 4 | Multiusuario con speaker diarization | 📋 Este documento |
| Datos | ≥100 sesiones de Ramón para base sólida | En progreso |

---

## 6. Tiempo estimado

| Tarea | Duración |
|---|---|
| Instalar pyannote.audio + modelos | 2h |
| Sistema de perfiles (crear/cargar/update) | 3h |
| Onboarding de nuevo usuario | 2h |
| Tests con 2-3 personas | 1h |
| **Total** | **~8 horas** |

---

## 7. Cuándo implementar

Después de Fase 3 completada (~2-3 semanas de Fase 1 funcionando con Ramón).
Necesitamos primero que el sistema individual sea sólido antes de añadir complejidad multiusuario.

---

## 8. Decisión

**Documentado, NO implementado hoy.**
