# B4 — Diagnóstico de servicios systemd FAILED (GX10)

- **Fecha**: 2026-08-17 14:39 CEST
- **Modo**: diagnóstico READ-ONLY — **ninguna reparación ejecutada**
- **TASK**: TASK-20260817-019 (B4, fase 1)
- **Método**: `systemctl --failed` + `systemctl status -l` + `journalctl -u <svc> -n 50` + verificación de ExecStart/venv/timers.

## Resumen

| Servicio | Último fallo | Código | Causa clasificada | Pronóstico |
|---|---|---|---|---|
| ura-audit-extra | 2026-08-17 05:00:01 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |
| ura-backup | 2026-08-17 04:00:00 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |
| ura-consolidate | 2026-08-17 05:00:01 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |
| ura-harden | 2026-08-17 05:00:01 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |
| ura-mutmut-daily | 2026-08-17 06:00:01 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |
| ura-reindex | 2026-08-17 05:00:01 | 203/EXEC | Dependencia rota (venv) — transitoria | ✅ Próxima ejecución OK |

## Hallazgo principal (causa raíz compartida)

Todos los servicios usan `.venv/bin/python3` (o `python`) como intérprete del ExecStart y fallaron con
**status=203/EXEC** (execve fallido: intérprete inexistente o no ejecutable) entre las 04:00 y 06:00 de hoy.

**Evidencia de recuperación automática**:
- `.venv/bin/python3` fue (re)creado el **2026-08-17 11:01:16** (mtime del symlink, verificado) — regeneración del venv de la mañana (Bloque B1).
- **`ura-maintenance-v2` (mismo patrón ExecStart) falló a las 06:00:01 y ejecutó OK a las 12:00:01**: "Deactivated successfully", 5.760s CPU, 16.7M peak — **prueba de que el venv actual funciona**.
- Los 6 servicios restantes corren de 04:00 a 06:00 (timers diarios), por lo que su próxima ejecución es mañana 2026-08-18 y **previsiblemente pasarán sin cambios**.

Causa raíz histórica del 203/EXEC en la madrugada: el `.venv` estaba roto/inexistente en ese momento (probablemente
eliminado en una regeneración fallida el 16-17/08). **El detalle exacto del estado del venv a las 04:00 es NO VERIFICABLE**
(ya no existe evidencia en disco); la evidencia circundante (recreación 11:01 + maintenance-v2 OK a las 12:00) es concluyente
para el pronóstico.

## Clasificación por categorías (según protocolo B4)

| Categoría | Servicios | Detalle |
|---|---|---|
| Falta de permisos | — | Ninguno (User=ramon correcto; scripts `-rw-r--r--` interpretados por python, no necesitan +x) |
| Script no encontrado | — | Todos los scripts existen: `auditoria_paralela.py`, `backup_assistant.py`, `consolidacion.py`, `hardening_audit.py`, `mutmut_daily.py`, `reindex_vectors.py` (verificado `ls -la scripts/pro/`) |
| **Dependencia rota (transitoria)** | **Los 6** | `.venv/bin/python3` no ejecutable en 04:00-06:00; regenerado 11:01:16 hoy |
| Configuración incorrecta | — | ExecStart correcto; `UnitFileState=static` esperado; timer existente por servicio |
| Servicio innecesario/legacy | — | Todos embebidos en timers diarios intencionales (B3 los mantiene) |

## Acciones propuestas (NO ejecutadas — requieren autorización)

1. **P1 (verificación pasiva, recomendada)**: no tocar nada; tras el disparo de mañana 04:00-06:00, comprobar
   `systemctl is-active ura-{backup,audit-extra,consolidate,harden,reindex,mutmut-daily}` y journal. Si aprueban:
   no hay nada más que hacer — el problema ya se auto-resolvió con el venv nuevo.
2. **P2 (verificación activa opcional)**: ejecutar manualmente `systemctl start ura-backup.service` (y el resto) una
   vez, para confirmar hoy mismo que pasan. *Requiere autorización (fase 2 de la tarea)*.
3. **P3 (prevención)**: el 203/EXEC por venv se volverá a producir si se regenera el `.venv` (p.ej. `pip install`,
   limpieza) dejando unidades con ExecStart apuntando al venv. Propuesta futura (fuera de alcance B4): documentar en
   `REFERENCIA_GX10.md` la restricción "no regenerar `.venv` sin validar `systemctl is-system-running`" o añadir
   `OnFailure=` a las unidades para alertar.

## Estado coordinación

- TASK-20260817-019 → `en_revision` (revisor: WEB). TERM libre, WEB ocupado.

## Referencias
- `systemctl --failed --no-legend` (14:39) → 6 unidades
- `systemctl status {svc}` → 203/EXEC en todas
- `journalctl -u ura-maintenance-v2 -n 5` → OK 12:00:01 con venv nuevo
- `stat .venv/bin/python3` → mtime 2026-08-17 11:01:16
- Timers: ura-backup 04:00, ura-audit-extra/consolidate/harden/reindex 05:00, ura-mutmut-daily 06:00, mantenidos