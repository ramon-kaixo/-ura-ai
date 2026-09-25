# Investigación de la tuneladora — 2026-08-18 (WEB)

## Qué es
Dos sistemas que comparten nombre:
1. `tuneladora_mejora.py` (v2.3) — pipeline de mejora continua: pre → refactor_plugins →
   pipeline_refactor → post, con checkpoint/ledger/presupuesto y política de promoción R1.
2. `tuneladora_pipeline.py` (runner) — pipeline de validación (preflight, static, dynamic,
   api_diff, index, integrity, verdict) con rollback por snapshot. LO LANZA el
   `watch_daemon.sh` (ura-watch-daemon.service) que observa scripts/pro/tuneladora/ y tests/.

## Por qué fallaba hoy (03:0x-03:5x) — Pipeline FAILED en bucle
1. **Disparo por ediciones masivas**: el watch_daemon reacciona a CADA close_write de
   tests/ y tuneladora/ con DEBOUNCE=2s. Hoy el WEB editó decenas de archivos
   (ruff --fix en scripts/, tests nuevos) → decenas de checks en cadena.
2. **Contención de I/O con el backup a la Mac**: el backup copiaba /home/ramon/URA COMPLETO
   (189GB modelos + 23GB archives) → I/O saturada → los checks tardaban/fallaban.
3. **vram_pressure_high** (guardian): ollama bajo presión → pytest/static lentos.
4. **Destello del model router** (Connection refused 03:25): el check con LLM fallaba.
5. En modo `check`, sofia NO se ejecuta (solo gate/fix) → "sofia: 0/0" es NORMAL, no un fallo.

## Por qué NO se perdió trabajo
El rollback restaura el SNAPSHOT que el propio check tomó al inicio (estado ya correcto
commiteado) → no revierte trabajo ajeno. Comportamiento seguro (fail-safe).

## Mejoras implementadas (watch_daemon v3.1)
- DEBOUNCE_SEC 2→6 y COOLDOWN 10→15 (estabilización de cambios masivos).
- Guard de recursos `_resources_ok()`: si hay backup a la Mac en curso o VRAM alta
  reciente → encolar en vez de lanzar (evita contención). Patrón `[r]sync` anti-automatch.
- §9 PENDIENTES_SUDO: reiniciar ura-watch-daemon.service (quedó inactive tras recargar).

## Qué más se observó (contexto)
- El backup se corrigió de raíz (SOURCE=solo repo, 309MB) → la contención desaparece.
- Heartbeat arreglado con drop-in ProtectHome=no (§8) → auto_dumps ya se escriben.
- La tuneladora NO estaba rota: 1115 líneas de éxito/aplicaciones en la hora previa.
