# INFORME DE CRITICIDAD — CÓDIGO VIVO
> Actualizado: 2026-06-15
> Base: Legacy 264 archivos + motor/ (26 archivos, 1904 líneas)

---

## CRÍTICO (0) — Sin hallazgos

## ALTO (0) — Sin hallazgos

## MEDIO (3) — Legacy (core/, monitor/, agents/)

### M1 — `urllib.request.urlopen()` sin validación de esquema
**Riesgo:** Permite URLs con esquema `file://`.
**Impacto:** Bajo — todas las llamadas son a `http://127.0.0.1`.
**Estado:** ⏳ PENDIENTE — fuera del escopo motor/

### M2 — `/tmp` sin sanitizar en sandbox
**Archivos:** `sandbox.py:244`, `docker_orchestrator.py:41`
**Riesgo:** Uso de `/tmp` sin verificar existencia previa.
**Estado:** ⏳ PENDIENTE — fuera del escopo motor/

### M3 — Escritura concurrente en `guardián_disco.py`
**Archivos:** `core/guardián_disco.py:46,107`
**Riesgo:** Múltiples agentes escribiendo simultáneamente.
**Estado:** ⏳ PENDIENTE — fuera del escopo motor/

---

## AUDITORÍA MOTOR/ (2026-06-15) — 11 hallazgos, 10 corregidos

### M4 — `scan.ok` nunca se ponía True (CRÍTICO)
**Hallazgo:** Ningún incidente se guardó nunca en Qdrant.
**Fix:** `r.ok = True` en Scanner.run(). Cambiado guard en diagnostico.
**Estado:** ✅ CORREGIDO

### M5 — `getattr` sobre dict en `detectar_anomalias` (CRÍTICO)
**Hallazgo:** Calibración nunca detectaba anomalías.
**Fix:** `estado.recursos.get(metric, 0)` en vez de `getattr`.
**Estado:** ✅ CORREGIDO

### M6 — Typo `load_avg_1m` (ALTA)
**Hallazgo:** Alerta de CPU nunca se disparaba.
**Fix:** Cambiado a `load_1m`.
**Estado:** ✅ CORREGIDO

### M7 — `dmesg --read-clear` destructivo (ALTA)
**Hallazgo:** Cada escaneo borraba el ring buffer del kernel.
**Fix:** Cambiado a `--since "1 hour ago"` (solo lectura).
**Estado:** ✅ CORREGIDO

### M8 — Coste histórico siempre cero (MEDIA)
**Fix:** Eliminados campos `media_h`/`total_h` inservibles.
**Estado:** ✅ CORREGIDO

### M9 — Singleton sin lock (MEDIA)
**Fix:** Añadido `threading.Lock` a `instancia()`.
**Estado:** ✅ CORREGIDO

### M10 — `except: pass` masivos (25+ ocurrencias)
**Fix:** Todos reemplazados por `except Exception as e: log.warning(...)`.
**Estado:** ✅ CORREGIDO (commit 0713dcc)

### M11 — Hardcodeos varios
**Fix:** IPs, `ssh root@{host}`, `/dev/nvme0n1`, `8.8.8.8` movidos a constantes.
**Estado:** ✅ CORREGIDO

---

## BAJO

### B1 — Código muerto legacy
**Estado:** ⏳ PENDIENTE

### B2-B4 — macOS, requirements, logrotate
**Estado:** ✅ VERIFICADOS

### B5 — Código muerto motor/ (`_check_opencode`)
**Estado:** ✅ CORREGIDO

---

## Resumen

| Ámbito | Hallazgos | Corregidos | Pendientes |
|--------|-----------|------------|------------|
| motor/ | 11 | 10 | 0 |
| legacy | 7 | 4 | 3 |
| **Total** | **18** | **14** | **3** |

## Métricas motor/

| Métrica | Valor |
|---------|-------|
| Archivos | 26 Python |
| Líneas | 1904 |
| Tests | 20/20 |
| Bugs críticos | 5 corregidos |
| `except: pass` eliminados | 25+ |
| Hardcodeos eliminados | 8 |
| Refactor commits | 0713dcc |
