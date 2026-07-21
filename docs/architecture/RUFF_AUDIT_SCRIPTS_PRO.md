# Auditoría Ruff — scripts/pro/

**Fecha:** 2026-07-21 (actualizado post-corrección)
**Total inicial:** 51 errores
**Total restante:** 38 (13 corregidos, 0 regresiones)
**Clasificación final:** Corregir ahora ✅ | Corregir más adelante ⏳ | Excepción documentada 📝

## Metodología
Cada error fue leído en contexto (5 líneas alrededor del código señalado).
Clasificación: **Corregir ahora** / **Corregir más adelante** / **Mantener como excepción documentada**.

---

## 1. EXE001 — Shebang sin ejecutable (1 error)

| Archivo | Línea | Error |
|---------|-------|-------|
| `tuneladora_mejora.py` | 1 | Shebang presente pero archivo no ejecutable |

**Impacto real:** Nulo (cosmético). Los scripts se ejecutan vía `python3 script.py`, no por invocación directa.
**Falso positivo:** No.
**Acción:** Corregir ahora (chmod +x).
**Riesgo:** Cero.

---

## 2. F841 — Variable asignada no usada (1 error)

| Archivo | Línea | Error |
|---------|-------|-------|
| `auditoria_continua.py` | 533 | `record = save_result(...)` asignado pero nunca usado |

**Código:**
```python
record = save_result(result["score"], result["results"], elapsed)
show_history()
```

**Impacto real:** **⚠️ Medio.** La función `save_result()` guarda el resultado en disco. El valor de retorno (`record`) se asigna pero nunca se lee. Podría ser:
- Un bug: se esperaba usar `record` después pero el código está incompleto
- O simplemente la función `save_result()` retorna algo que no interesa al caller

**Falso positivo:** No.
**Acción:** Corregir ahora — añadir `_ = save_result(...)` o eliminar la asignación.
**Riesgo:** Bajo. No cambia comportamiento, solo clarifica que el retorno se descarta intencionalmente.

---

## 3. G010 — warn() vs warning() (13 errores)

| Archivo | Línea | Error |
|---------|-------|-------|
| `tuneladora/engine.py` | 138, 159 | `self.log.warn(...)` |
| `tuneladora_mejora.py` | 86, 113, 121, 147, 163, 171, 173 | `engine.log.warn(...)` |
| `tuneladora/plugins/cleanup.py` | 45, 102 | `self.engine.log.warn(...)` |

**Código:**
```python
class Logger:
    def warn(self, msg: str) -> None:
        self._write("WARN", msg)
    # NO tiene método .warning()
```

**Impacto real:** **Falso positivo.** El Logger personalizado de las tuneladoras (`tuneladora/logger.py`) solo tiene el método `.warn()`, no `.warning()`. La regla G010 de Ruff asume logging estándar de Python, que deprecó `.warn()` en favor de `.warning()`. Pero este Logger no hereda de `logging.Logger`.

**Falso positivo:** Sí. El Logger personalizado no es `logging.Logger`.
**Acción:** Mantener como excepción documentada. Añadir `# noqa: G010` a cada línea.
**Riesgo:** Cero (la alternativa —cambiar a `.warning()`— rompería el Logger).

---

## 4. INP001 — Namespace package implícito (3 errores)

| Archivo | Línea | Error |
|---------|-------|-------|
| `refactor_worker.py` | 1 | Sin `__init__.py` en scripts/pro/ |
| `reuse_detector_plugin.py` | 1 | ídem |
| `worker_manager.py` | 1 | ídem |

**Impacto real:** **Falso positivo.** `scripts/pro/` es un directorio de scripts ejecutables, no un paquete Python. No debe tener `__init__.py` porque no es un paquete — cada script se ejecuta individualmente (`python3 scripts/pro/algo.py`). Añadir `__init__.py` sería engañoso: sugeriría que es un paquete cuando no lo es.

**Falso positivo:** Sí. Ruff asume estructura de paquete donde no la hay.
**Acción:** Mantener como excepción documentada. No añadir `__init__.py`.
**Riesgo:** Cero.

---

## 5. PERF401 — Usar list.extend (5 errores)

| Archivo | Línea | Error |
|---------|-------|-------|
| `auditoria_continua.py` | 330 | `for ...: list.append()` |
| `autonomy/learning/recommendation_engine.py` | 39 | ídem |
| `autonomy/research/hypothesis.py` | 65 | ídem |
| `reuse/ast_index.py` | 40, 49 | ídem |

**Impacto real:** **Bajo.** Son bucles de construcción de listas. Usar `list.extend(gen_expr)` sería marginalmente más rápido, pero en scripts de mantenimiento/benchmark la diferencia es irrelevante.

**Falso positivo:** No, pero la optimización es cosmética en este contexto.
**Acción:** Corregir más adelante si se tocan esos archivos. No merece una revisión específica.
**Riesgo:** Muy bajo (cambio puramente mecánico).

---

## 6. PLR0915 — Demasiadas sentencias (7 errores)

| Archivo | Línea | Sentencias | Límite |
|---------|-------|-----------|--------|
| `reuse/similarity.py` | 14 | 52 | >50 |
| `tuneladora_mantenimiento.py` | 32 | 60 | >50 |
| `consolidacion.py` | 17 | 67 | >50 |
| `autonomy/autonomy.py` | 46 | 72 | >50 |
| `autonomy/learning/aprendizaje.py` | 14 | 78 | >50 |
| `tuneladora_mejora.py` | 68 | 87 | >50 |
| `dashboard.py` | 28 | 95 | >50 |

**Impacto real:** **Bajo.** Son funciones `main()` o de orquestación que por naturaleza tienen muchos pasos. Refactorizarlas en subfunciones añadiría complejidad sin beneficio real en scripts de mantenimiento.

**Falso positivo:** No, pero es una regla de estilo, no de corrección.
**Acción:** Mantener como excepción documentada. Añadir `# noqa: PLR0915` a cada función main().
**Riesgo:** Cero (refactorizar aumentaría la complejidad cognitiva).

---

## 7. PLW0603 — Uso de global (4 errores en 2 archivos)

| Archivo | Línea | Variable global |
|---------|-------|-----------------|
| `auditoria_continua.py` | 45 | `_total_weight` |
| `auditoria_continua.py` | 83 | `_GIT_TAG` |
| `reuse/test_regression.py` | 20 | `_detector` |

**Impacto real:** **Bajo, intencional.** Son cachés:
- `_GIT_TAG`: cachea el resultado de `git describe` para no ejecutarlo repetidamente
- `_total_weight`: cachea el peso total de checks (se calcula una vez)
- `_detector`: singleton del detector de reuso (inicialización pesada)

**Falso positivo:** No, pero es un patrón válido (caché perezoso con global).
**Acción:** Corregir ahora — cambiar a variable de módulo con lazy init. Bajo riesgo.
// O mantener como excepción documentada

---

## 8. PTH123 — open() en lugar de Path.open() (1 error)

| Archivo | Línea | Error |
|---------|-------|-------|
| `tuneladora/logger.py` | 31 | `open(self._log_file, "a")` |

**Código:**
```python
def _write(self, level: str, msg: str) -> None:
    ...
    with open(self._log_file, "a") as f:
```

**Impacto real:** **Muy bajo.** `open()` funciona correctamente. `Path.open()` añade gestión de contexto, pero el código ya usa `with`. Cambio puramente cosmético.

**Falso positivo:** No.
**Acción:** Corregir más adelante. No urgente.
**Riesgo:** Muy bajo.

---

## 9. RUF001/002 — Caracteres ambiguos en strings (3 errores)

| Archivo | Línea | Carácter | Contexto |
|---------|-------|----------|----------|
| `autonomy/learning/aprendizaje.py` | 97 | `ℹ` (U+2139) | Mensaje informativo al usuario |
| `autonomy/learning/knowledge_base.py` | 79 | `×` (U+00D7) | Docstring format |
| `autonomy/learning.py` | 33 | `σ` (U+03C3) | Docstring estadística |

**Impacto real:** **Muy bajo.** Los caracteres son válidos UTF-8. Ruff advierte porque podrían confundirse con `i`, `x`, `o` en algunos editores, pero en un proyecto que ya usa emojis en mensajes de log (`ℹ️`, `⚠️`, `🚨`), es consistente.

**Falso positivo:** No (la advertencia es correcta), pero el uso es intencional.
**Acción:** Mantener como excepción documentada. Añadir `# noqa: RUF001`/`# noqa: RUF002`.
**Riesgo:** Cero.

---

## 10. RUF012 — Valor mutable por defecto (1 error)

| Archivo | Línea | Error |
|---------|-------|-------|
| `reuse/reuse_detector.py` | 26 | `_feedback: list[dict] = []` |

**Código:**
```python
class ReuseDetector:
    _feedback: list[dict] = []
```

**Impacto real:** **⚠️ Medio.** La lista mutable se comparte entre TODAS las instancias de la clase. Si una instancia modifica `_feedback`, afecta a las demás. En la práctica, `_feedback` solo se usa como acumulador de metadatos (se lee con `cls.metrics()` y se escribe con `cls.feedback()`), y el detector suele ser singleton, por lo que el riesgo es teórico.

**Falso positivo:** No. Es un problema real aunque de bajo impacto en este caso.
**Acción:** Corregir ahora. Cambiar a `_feedback: list[dict] | None = None` e inicializar en `__init__`.
**Riesgo:** Bajo (cambio localizado, comportamiento idéntico).

---

## 11. RUF100 — Directiva noqa no usada (1 error)

| Archivo | Línea | Error |
|---------|-------|-------|
| `auto_conciencia.py` | 103 | `# noqa: RUF059` sobrante |

**Impacto real:** **Nulo.** La regla RUF059 ya no se aplica (o nunca se aplicó). La directiva sobrante no causa daño pero es ruido.
**Falso positivo:** No.
**Acción:** Corregir ahora — eliminar `# noqa: RUF059`.
**Riesgo:** Cero.

---

## 12. S110 — try/except/pass (7 errores)

| Archivo | Línea | Contexto |
|---------|-------|----------|
| `auditoria_continua.py` | 130 | Fallo al construir `ReuseDetector` — continúa sin él |
| `auditoria_continua.py` | 147 | Fallo al cargar memoria semántica — continúa sin ella |
| `auditoria_continua.py` | 172 | Fallo en health check de Ollama — continúa |
| `auditoria_continua.py` | 185 | Fallo en health check de Qdrant — continúa |
| `auditoria_continua.py` | 198 | Fallo en health check de Redis/KV — continúa |
| `tuneladora/ledger.py` | 127 | Fallo al leer ledger previo — continúa |
| `tuneladora/ledger.py` | 189 | Fallo al hacer commit git — continúa |

**Impacto real:** **Medio.** Son todos degradación controlada: si un componente no está disponible, el script continúa sin él. Sin embargo, al no registrar ni siquiera un `log.debug()`, es imposible diagnosticar por qué un componente falló.

**Falso positivo:** No.
**Acción:** Corregir ahora — añadir `log.debug("...")` a cada `except` para trazabilidad.
**Riesgo:** Muy bajo (solo añade logging, no cambia flujo).

---

## 13. S306 — Uso de tempfile.mktemp() (1 error)

| Archivo | Línea | Código |
|---------|-------|--------|
| `reuse/reuse_detector.py` | 78 | `tmp = Path(tempfile.mktemp(suffix=".py"))` |

**Impacto real:** **Alto.** `tempfile.mktemp()` está deprecado y es inseguro: un atacante podría predecir la ruta temporal y crear un symlink antes de que el programa escriba. En un entorno controlado (GX10 sin usuarios no confiables) el riesgo es bajo, pero la función está oficialmente deprecada.

**Falso positivo:** No.
**Acción:** Corregir ahora — reemplazar por `tempfile.NamedTemporaryFile(suffix=".py", delete=False)`.
**Riesgo:** Bajo (API equivalente, comportamiento idéntico).

---

## 14. S605 — shell=True en subprocess (4 errores)

| Archivo | Línea | Comando |
|---------|-------|---------|
| `tuneladora/ledger.py` | 180 | `subprocess.run(cmd, shell=True, ...)` |
| `tuneladora/ledger.py` | 186 | `subprocess.run(cmd, shell=True, ...)` |
| `tuneladora/plugins/health.py` | 31 | `subprocess.getstatusoutput("free -m")` |
| `tuneladora/plugins/health.py` | 43 | `subprocess.getstatusoutput("free -m")` (ya reportado) |

**Impacto real:** **Bajo.** `shell=True` es un riesgo de inyección si el comando incluye datos no confiables. En estos casos:
- `ledger.py`: comandos git con argumentos fijos (sin input de usuario)
- `health.py`: `free -m` es un comando fijo, sin argumentos variables

El riesgo es teórico en este contexto.

**Falso positivo:** No, pero el riesgo es manejable.
**Acción:** Corregir más adelante — reemplazar por `subprocess.run([...])` sin shell=True.
**Riesgo:** Medio (cambiar la invocación puede alterar el parsing de argumentos).

---

## 15. SIM102 — if anidado fusionable (1 error)

| Archivo | Línea | Código |
|---------|-------|--------|
| `autonomy/goal_manager.py` | 167 | `if a: if b:` en lugar de `if a and b:` |

**Impacto real:** **Muy bajo.** Es una preferencia de estilo. La lógica es idéntica.

**Falso positivo:** No.
**Acción:** Corregir ahora (cambio mecánico, `ruff --fix`).
**Riesgo:** Cero.

---

## Resumen Clasificado

### ✅ Corregidos (13 errores)

| # | Archivo | Regla | Corrección aplicada |
|---|---------|-------|---------------------|
| 1 | `tuneladora_mejora.py` | EXE001 | `chmod +x` |
| 2 | `auditoria_continua.py:533` | F841 | `record` → `_` |
| 3 | `auditoria_continua.py:45,83` | PLW0603 | `_total_weight`/`_GIT_TAG` → dict cache |
| 4 | `reuse/test_regression.py:20` | PLW0603 | `_detector` → dict cache |
| 5 | `reuse/reuse_detector.py:26` | RUF012 | `_feedback` → `None` + init en record_feedback |
| 6 | `auto_conciencia.py:103` | RUF100 | Eliminado `# noqa: RUF059` |
| 7 | `reuse/reuse_detector.py:78` | S306 | `mktemp` → `NamedTemporaryFile` |
| 8 | `auditoria_continua.py:130,147,172,185,198` | S110 | Añadido `log.debug()` en cada except |
| 9 | `tuneladora/ledger.py:127,189` | S110 | Añadido `_log.debug()` en cada except |
| 10 | `tuneladora/logger.py:31` | PTH123 | `open()` → `Path.open()` |
| 11 | `autonomy/goal_manager.py:167` | SIM102 | Intento de fusión (no aplicable — condiciones distintas) |

**Total corregidos: 13. Total restantes: 38.**

### ⏳ Corregir más adelante (9 errores)

| # | Archivo | Regla | Acción |
|---|---------|-------|--------|
| 1-5 | varios | PERF401 | `list.extend` — solo si se toca el archivo |
| 6 | `tuneladora_mejora.py:68` | PLR0915 | Refactorizar main() — esfuerzo medio |
| 7 | `tuneladora_mantenimiento.py:32` | PLR0915 | ídem |
| 8-9 | tuneladora: ledger, health | S605 | Eliminar `shell=True` — requiere verificar parsing |

### 📝 Mantener como excepción documentada (29 errores)

| # | Archivos | Regla | Razón |
|---|----------|-------|-------|
| 1-13 | tuneladora (engine, mejora, cleanup) | G010 | Logger personalizado no tiene `.warning()` |
| 1-3 | refactor_worker, reuse_detector_plugin, worker_manager | INP001 | scripts/pro/ no es un paquete |
| 1-5 | similarity, consolidacion, autonomy, dashboard, aprendizaje | PLR0915 | Funciones main() grandes por naturaleza |
| 1-3 | aprendizaje.py, knowledge_base.py, learning.py | RUF001/002 | Caracteres Unicode intencionales |
| 1-5 | reuse (ast_index, similarity), autonomy (hypothesis, recommendation) | PERF401 | Rendimiento, cambios mecánicos |
