# 📋 CONSULTA A EXPERTOS — Tuneladora Suprema

## Prompt formal para solicitar revisión de arquitectura

---

## 🎯 Perfiles de Especialistas Necesarios

### 1. Ingeniero en Sistemas de Refactorización Automática
**Buscar en**: GitHub, LinkedIn, foros de Python (especialmente `comby`, `ast-grep`, `libcst`, `bowler`)
**Experiencia**: Google Kythe, Uber Piranha, Meta codemod, Instagram libcst
**Qué evaluará**:
- Pipeline cascada 6.7B → 14B → auto-reglas
- Tasa de éxito vs tiempo por función
- Estrategia de chunking y contexto dinámico
- Handle de errores de sintaxis post-LLM

**Tags de búsqueda**: `codemod`, `ast refactoring`, `program transformation`, `large scale code modification`

### 2. Arquitecto de Mantenimiento Predictivo de Código
**Buscar en**: Comunidades SonarQube, CodeClimate, Grafana, Prometheus
**Experiencia**: Sistemas de salud de código, detección de degradación, quality gates
**Qué evaluará**:
- Sistema de alertas tempranas de degradación
- Jerarquía temporal (1h/6h/24h)
- Métricas de calidad vs esfuerzo
- Puntos de decisión para rollback automático

**Tags de búsqueda**: `code health`, `technical debt detection`, `quality gates`, `predictive maintenance`

### 3. Experto en Orquestación Temporal y Automatización
**Buscar en**: Comunidades systemd, Airflow, Prefect, Temporal.io
**Experiencia**: Sistemas de planificación, cron, event-driven automation, rate limiting
**Qué evaluará**:
- Jerarquía temporal óptima
- Prevención de solapamiento de procesos
- Timeout y retry strategies
- Priorización bajo presión de recursos

**Tags de búsqueda**: `workflow orchestration`, `cron optimization`, `systemd timers`, `task scheduling`

### 4. Especialista en Auto-Aprendizaje para Sistemas de Código
**Buscar en**: Stanford PLSE, Snorkel AI, Weak Supervision, Active Learning communities
**Experiencia**: Sistemas que aprenden de sus propios errores, feedback loops, confidence scoring
**Qué evaluará**:
- Bucle watermarks → reglas auto
- Sistema de confianza (umbral 0.5, ±0.1/0.2 por acierto/fallo)
- Política de olvido (20 ciclos sin uso)
- Detección de falsos positivos

**Tags de búsqueda**: `active learning for code`, `weak supervision`, `self-healing systems`, `program repair`

---

## 📝 Prompt de Consulta (para enviar a cada experto)

```
ASUNTO: Consulta técnica — Arquitectura de refactorización automática con LLM + herramientas deterministas

CONTEXTO:
Sistema URA — agente autónomo de mejora continua de código Python.
Hardware: NVIDIA GX10 (128GB RAM unificada, GPU Blackwell).
Modelos: Ollama local (deepseek-coder:6.7b, qwen2.5-coder:14b, qwen3:32b-q8_0).
Repo: ~900 archivos .py, ~165K líneas, 107 funciones >80 líneas (monstruos).

ARQUITECTURA ACTUAL (ya implementada):
https://github.com/anomalyco/opencode/issues (o adjunto)

[Se adjunta docs/ARQUITECTURA_REFACTOR.md y docs/PROYECTO_TUNELADORA_SUPREMA.md]

PREGUNTAS ESPECÍFICAS PARA [NOMBRE_DEL_EXPERTO]:

{ preguntas_específicas }

CONTEXTO ADICIONAL:
- El sistema ya tiene 9 reglas built-in para reparación determinista de F821
- Auto-aprendizaje: cuando un error se repite ≥3 ciclos, se genera regla automática
- Tasa de éxito actual: deepseek-coder:6.7b 62.5%, qwen2.5-coder:14b 40%
- El refactor es en funciones individuales (no archivos completos)
- Cada función se refactoriza con prompt de 6 capas (identidad, contexto, objetivo, restricciones, formato, verificación)
- Workers: 4 en paralelo, contexto dinámico (num_predict = tokens × 1.5)
```

---

## ❓ Preguntas Específicas por Experto

### Para el Ingeniero de Refactorización Automática

```
1. ¿El pipeline cascada (6.7B → fallback 14B → auto_reglas determinista) 
   es óptimo? ¿Recomendarías otro orden o estrategia?

2. deepseek-coder:6.7b está dando 62.5% de éxito vs 40% del 
   qwen2.5-coder:14b. ¿Tiene sentido usar el 6.7B como principal?

3. ¿El chunking por función individual es mejor que por archivo completo? 
   Nuestro chunking usa AST para extraer la función exacta.

4. ¿Recomiendas algún sistema de versionado de transformaciones 
   (ej: mantener antes/después para rollback quirúrgico)?

5. ¿Has trabajado con ast-grep (sg) o comby para post-procesado 
   de código generado por LLM? ¿Recomiendas alguna herramienta 
   específica para reparar imports faltantes?

6. ¿El prompt de 6 capas (identidad, contexto, objetivo, 
   restricciones, formato, verificación) es la estructura óptima?
```

### Para el Arquitecto de Mantenimiento Predictivo

```
1. ¿La jerarquía temporal 1h (health) / 6h (ciclo completo) / 
   24h (mantenimiento profundo) es adecuada? ¿Ajustarías frecuencias?

2. ¿Qué métricas adicionales monitorearías para detectar 
   degradación de código ANTES de que cause errores?

3. Nuestro sistema actual de alertas: 
   - Zombies >0 → alerta
   - RAM >90GB → alerta
   - F821 sube >10% respecto al baseline → alerta
   - Tasa de éxito del refactor <40% → alerta
   ¿Añadirías/quitarías alguna?

4. ¿Cómo recomiendas manejar el solapamiento entre ciclos 
   (ej: un refactor que tarda más de 6h)?

5. ¿Recomiendas un sistema de quality gates por fases 
   (no pasar a la siguiente fase si la actual no cumple)?

6. ¿Tiene sentido un dashboard en tiempo real con las métricas 
   del sistema (http://10.164.1.99:11435/metrics)?
```

### Para el Experto en Orquestación Temporal

```
1. El sistema tiene 3 timers systemd (1h, 6h, 24h). 
   ¿Recomiendas timers independientes o un solo orquestador 
   con despertador periódico?

2. ¿Cómo prevenir el solapamiento si un ciclo de 6h 
   tarda más de 6h? Actualmente: timeout=3600s + lockfile.

3. Timeouts actuales por rodillo:
   - Diagnóstico: 5min
   - Refactor: 60min (con workers en paralelo)
   - Backup: 5min
   - Mantenimiento: 10min
   ¿Son adecuados o recomiendas ajustes?

4. ¿Recomiendas priorización de rodillos? 
   Ej: si RAM >90GB, saltar refactor y solo hacer diagnóstico.

5. ¿El sistema de health check cada 1h es suficiente o 
   debería ser más frecuente (ej: 15min)?
```

### Para el Especialista en Auto-Aprendizaje

```
1. Nuestro sistema actual: watermark se genera cuando un 
   patrón de error aparece ≥3 ciclos. ¿Es 3 el umbral correcto?

2. Sistema de confianza de reglas:
   - Nueva regla: confianza 0.5
   - Acierto: +0.1
   - Fallo: -0.2
   - Se elimina si confianza <0.3
   - Se aplica solo si confianza ≥0.5
   ¿Recomiendas ajustar estos valores?

3. Política de olvido: una regla no usada en 20 ciclos 
   (5 días) se elimina. ¿Es correcto?

4. Tenemos 9 reglas built-in (imports estándar) con 
   confianza 0.85-0.95. ¿Tiene sentido que las built-in 
   también aprendan (subir/bajar confianza) o deben ser fijas?

5. ¿Recomiendas un sistema de "sospecha" para reglas 
   que antes funcionaban pero ahora fallan? 
   (ej: si una regla con confianza 0.8 falla 2 veces seguidas, 
   ponerla en cuarentena automática)

6. ¿Cómo detectar falsos positivos en la generación de reglas? 
   (ej: un error que aparece 3 veces por coincidencia, 
   no porque sea un patrón real)
```

---

## 📤 Canales de Consulta

| Canal | Formato | Para |
|-------|---------|------|
| **GitHub Issues** | Público | Compartir con comunidad open source |
| **Discord/URA Community** | Privado | Consulta directa con expertos conocidos |
| **Stack Overflow / Code Review SE** | Público | Preguntas específicas sobre arquitectura |
| **LinkedIn / Email directo** | Privado | Contactar expertos identificados |

---

## 📦 Documentación Adjunta para Enviar

Al hacer la consulta, adjuntar estos 3 archivos:

1. `docs/ARQUITECTURA_REFACTOR.md` — Pipeline técnico actual
2. `docs/PROYECTO_TUNELADORA_SUPREMA.md` — Proyecto de fusión
3. `.config/prompts/unified_prompts.json` — Config unificada

---

*Documento de consulta. Preparado por el Comité de los Cuatro Expertos (👮, 🦞, 🧩, ⚡).*
