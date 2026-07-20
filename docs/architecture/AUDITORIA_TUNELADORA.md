# AUDITORÍA TUNELADORA — Pipeline de Mejora Continua

**Fecha:** 2026-07-20  
**Analista:** Pipeline Specialist  
**Componentes:** `tuneladora_master.py` (250 líneas), `launch_refactor_gx10.sh`, `openclaw_firmador.py`

---

## Resumen

La tuneladora es un orquestador de mejora continua que ejecuta un pipeline delta (diario) o profundo (mensual). Está diseñada como un ciclo autónomo con handshake vía sistema nervioso (`.nervioso/`). El concepto es sólido, pero la implementación tiene múltiples defectos que reducen su fiabilidad.

---

## Hallazgos

### H1 — BUG: `helper1` usa string literal en lugar de variable (MODIFICADO)

**Archivo:** `tuneladora_master.py:135`  
**Código:** `delta_dir = Path("NERVIOSO") / "delta_snapshots"`  
**Problema:** Usa el string literal `"NERVIOSO"` en lugar de la variable global `NERVIOSO`.  
**Impacto:** El modo profundo intenta limpiar `./NERVIOSO/delta_snapshots` en lugar de `URA_ROOT/.nervioso/delta_snapshots`. La limpieza no tiene efecto.  
**Severidad:** 🔴 Alta

### H2 — Import lazy después de trabajo pesado

**Archivo:** `tuneladora_master.py:103`  
**Código:** `from openclaw_firmador import delta_snapshot` dentro de `modo_delta()`  
**Problema:** El import ocurre DESPUÉS de ejecutar el subprocess de 4 workers (línea 90-96). Si el import falla (script ejecutado desde directorio incorrecto), el modo delta falla tras haber hecho todo el trabajo, perdiendo el resultado.  
**Solución:** Mover el import al inicio de la función o a nivel de módulo.  
**Severidad:** 🟡 Media

### H3 — Argumentos documentados no implementados

**Archivo:** `tuneladora_master.py:4-7`  
**Código:** Los flags `--use-delta-check`, `--force-all`, `--intensive-audit` aparecen en el docstring pero no hay parser de argumentos. Solo `--force-all` se evalúa mediante `sys.argv`.  
**Problema:** `--help` no funciona. `--intensive-audit` no tiene efecto.  
**Solución:** Implementar `argparse`.  
**Severidad:** 🟡 Media

### H4 — `os.chdir` en import time

**Archivo:** `tuneladora_master.py:29`  
**Código:** `os.chdir(str(URA_ROOT))`  
**Problema:** Cambiar el directorio de trabajo al importar el módulo es un side-effect. Si otro script importa este módulo, su cwd cambia inesperadamente.  
**Solución:** Mover a `main()`.  
**Severidad:** 🟡 Media

### H5 — Typo en mensaje de helper4

**Archivo:** `tuneladora_master.py:169`  
**Código:** `return "REG RESION"`  
**Problema:** Debería ser `"REGRESSION"`.  
**Severidad:** 🔵 Baja

### H6 — Ruff no usa venv

**Archivo:** `tuneladora_master.py:191`  
**Código:** `["ruff", "check", ...]`  
**Problema:** Asume que `ruff` está en PATH. Después de la migración a `.venv/`, debería ser `.venv/bin/ruff`.  
**Severidad:** 🟡 Media (fallará si ruff no está instalado globalmente)

### H7 — Timeout de 24h sin fallback

**Archivo:** `tuneladora_master.py:94,210`  
**Código:** `timeout=86400`  
**Problema:** Si `launch_refactor_gx10.sh` se cuelga, la tuneladora espera 24 horas antes de fallar. No hay watchdog interno ni escalado de timeout.  
**Solución:** Timeout más razonable (ej: 3600s = 1h) y reintento.  
**Severidad:** 🟡 Media

### H8 — `rm -rf` vía subprocess

**Archivo:** `tuneladora_master.py:137`  
**Código:** `subprocess.run(["rm", "-rf", str(delta_dir)], check=False)`  
**Problema:** Debería usar `shutil.rmtree(delta_dir, ignore_errors=True)`. Más seguro, sin dependencia de comandos externos.  
**Severidad:** 🔵 Baja

### H9 — Sin try/except en delta_snapshot

**Archivo:** `tuneladora_master.py:103-105`  
**Código:** Llamada a `delta_snapshot("ultimo_ciclo")` sin protección.  
**Problema:** Si `delta_snapshot` falla, todo el modo delta falla con excepción no manejada. El informe final nunca se loggea.  
**Severidad:** 🟡 Media

### H10 — Ruta de log inconsistente

**Archivo:** `tuneladora_master.py:9,26`  
**Código:** Docstring dice `/var/log/ura_tunel.log`, código usa `URA_ROOT/logs/ura_tunel.log`.  
**Problema:** Inconsistencia documentación vs implementación.  
**Severidad:** 🔵 Baja

### H11 — Redundancia: helper5 duplica lógica

**Archivo:** `tuneladora_master.py:172-176` vs `103-105`  
**Código:** `helper5()` es idéntica a las líneas 103-105.  
**Problema:** Código duplicado. Si se modifica una, la otra queda inconsistente.  
**Severidad:** 🔵 Baja

### H12 — Sin logging de errores en subprocess

**Archivo:** `tuneladora_master.py:90-96,206-212`  
**Código:** `result = subprocess.run([...], capture_output=True, check=False)`  
**Problema:** No se verifica `result.returncode`. Se extrae `result.stdout` y `result.stderr` pero solo los últimos 500/200 caracteres. Si el error está al principio, se pierde.  
**Severidad:** 🟡 Media

---

## Matriz de hallazgos

| # | Severidad | Tipo | Archivo:línea |
|---|-----------|------|---------------|
| H1 | 🔴 Alta | Bug | `tuneladora_master.py:135` |
| H2 | 🟡 Media | Riesgo | `tuneladora_master.py:103` |
| H3 | 🟡 Media | Mejora | `tuneladora_master.py:4-7` |
| H4 | 🟡 Media | Diseño | `tuneladora_master.py:29` |
| H5 | 🔵 Baja | Cosmético | `tuneladora_master.py:169` |
| H6 | 🟡 Media | Config | `tuneladora_master.py:191` |
| H7 | 🟡 Media | Robustez | `tuneladora_master.py:94,210` |
| H8 | 🔵 Baja | Mejora | `tuneladora_master.py:137` |
| H9 | 🟡 Media | Robustez | `tuneladora_master.py:103-105` |
| H10 | 🔵 Baja | Doc | `tuneladora_master.py:9,26` |
| H11 | 🔵 Baja | Código | `helper5` vs inline |
| H12 | 🟡 Media | Monitoreo | `tuneladora_master.py:90-96` |

---

## Conclusión

**El pipeline funciona en producción porque:** el timer systemd lo ejecuta desde el directorio correcto, `openclaw_firmador` está en el path, y el modo delta es el predeterminado (que no usa `helper1`).

**El bug H1 (`helper1` con `Path("NERVIOSO")` literal) hace que la limpieza del modo profundo sea inefectiva.** Como el modo profundo solo corre el día 1 de mes, nadie lo ha notado.

**Riesgo mayor:** Si `ruff` no está en PATH o el import de `openclaw_firmador` falla, el pipeline falla silenciosamente (captura stdout/stderr pero no verifica returncode).

**Puntuación:** 6/10 — Funcional pero frágil. El concepto es bueno, la implementación necesita hardening.
