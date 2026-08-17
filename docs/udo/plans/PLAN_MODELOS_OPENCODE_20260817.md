# PLAN — Solución integral de los problemas con modelos en OpenCode (infra URA)

**Fecha:** 2026-08-17 · **Autor:** WEB (ASUS) · **Estado:** PROPUESTA (pendiente revisión/veredicto coordenador)

## 1. Contexto (qué se padece)

1. La Web de OpenCode (`opencode.service`, puerto 8081, v1.18.18, rootfs `ro`) falla con varios modelos: `llama3.3:70b` ("does not support thinking", 7 errores hoy), `deepseek-v4-pro` ("Insufficient balance"), y `server unavailable key=openclaw` en cada sesión (24 fallos hoy).
2. **`opencode run` no ejecuta herramientas** con los modelos actuales: el modelo SÍ emite la tool call (verificado: `{"name": "bash", ...}`), pero opencode la imprime sin ejecutarla.

## 2. Diagnóstico verificado (evidencia, no conjetura)

| # | Causa | Evidencia |
|---|-------|-----------|
| C1 | **Config MCP fantasma**: `mcp.openclaw` → `npx -y @opencode/openclaw-mcp` (paquete **404 en npm**, gateway retirado `c6d60c8c`) | `server unavailable key=openclaw` ×24 hoy; `npm view`/`curl registry` → `404 Not Found` |
| C2 | **`reasoning: true`** en modelos que **no soportan thinking**: `llama3.3:70b`, `codestral:22b`, `qwen2.5-coder:14b/32b` | `ollama show` capabilities sin `thinking`; log: `"llama3.3:70b" does not support thinking` ×7 hoy |
| C3 | **Modelo nube sin saldo**: `deepseek-v4-pro` (provider opencode) | `Insufficient balance` + URL billing opencode.ai hoy 16:44 |
| C4 | **Rootfs RO**: `/` montado `ro` → opencode no puede crear lock/sesión: `EROFS: mkdir '/home/ramon/.local/state/opencode/locks/*.lock'` | Log run 54cbe1f1; `mount` muestra `/ ro`; `touch` falla en `~/.local/state/opencode` y `~/.cache/opencode` |
| C4b | Rootfs RO también rompe caché npm (`~/.npm` RO) y snapshots git de opencode | `npm error` EROFS `~/.npm/_logs`; `unable to unlink ... Operación no permitida` |

**Cadena del síntoma `opencode run`**: rootfs RO (C4) → `opencode run` arranca en modo degradado, sin lock → modelo stream con tool call → opencode no puede procesar/ejecutar la tool → imprime JSON crudo y termina. Y las sesiones web fallan además por C1/C2/C3.

> **NOTA (v2, 2026-08-17 ~22:00): esta cadena fue REFUTADA parcialmente por experimento** — ver §10. El rootfs RO no es la causa del no-ejecutar tools; es la causa del error EROFS de caché/snapshot (cosmético).

## 3. Objetivo

Que OpenCode (web y run CLI) funcione con los modelos locales Ollama: ejecute herramientas, sin errores de thinking, sin MCP fantasma, con rootfs RW.

## 4. Acciones propuestas (en orden)

| Paso | Acción | Quién | Riesgo | Reversible |
|------|--------|-------|--------|------------|
| P1 | `sudo mount -o remount,rw /` (+ revisar fstab, `rw,errors=remount-ro` ya documentado como FIX previo 2026-07-19 pero volvió a `ro`) | RAMÓN (sudo) | bajo | sí (`remount,ro`) |
| P2 | Backup `cp ~/.config/opencode/opencode.json /tmp/opencode/opencode.json.bak-20260817` | WEB | nulo | - |
| P3 | Editar `~/.config/opencode/opencode.json`: eliminar bloque `mcp.openclaw`; quitar `reasoning: true` de `llama3.3:70b`, `codestral:22b`, `qwen2.5-coder:14b`, `qwen2.5-coder:32b`; **dejar** `reasoning: true` solo en `deepseek-r1:14b` y `qwen3:32b-q8_0` (sí soportan thinking) | WEB | bajo (backup previo) | sí (restaurar backup) |
| P4 | Decisión humana: `deepseek-v4-pro` → recargar saldo opencode.ai o eliminarlo de la config hasta entonces | RAMÓN | - | - |
| P5 | Reiniciar servicio: `sudo systemctl restart opencode.service` (config no hot-reload; AGENTS.md v1.6) | RAMÓN (sudo) o WEB con sudo | medio (caída breve web; Restart=always) | sí |
| P6 | Verificación web + run CLI (sección 6) | WEB | nulo | - |

**No hacer**: no borrar modelos de Ollama; no cambiar el modelo por defecto a nube/pago; no tocar ramas 027/029; no editar la config de la Mac; no reintentar `npx @opencode/openclaw-mcp`.

## 5. Mínimos obligatorios (criterios de éxito)

1. `mount | grep "on / "` → `rw` (o evidencia de alternativa RW para `~/.local/state` y `~/.cache`).
2. `opencode run --model ollama/qwen2.5-coder:32b "usa la herramienta bash para ejecutar: echo OK"` → **ejecuta** la tool y devuelve salida (no JSON crudo).
3. Nueva sesión web con `qwen3:32b-q8_0` SIN errores thinking; con `llama3.3:70b` sin el error "does not support thinking".
4. Log sin `server unavailable key=openclaw` en sesiones nuevas.
5. `ollama ps` y model-router `/health` siguen OK (regresión cero).

## 6. Validación (comandos)

```bash
# 6.1 rootfs RW
grep " / " /proc/mounts
# 6.2 run con herramientas (debe EJECUTAR, no imprimir JSON)
~/.opencode/bin/opencode run --model ollama/qwen2.5-coder:32b "usa bash para ejecutar echo PLAN_OK y muéstralo"
# 6.3 sin MCP fantasma
grep -a "server unavailable" ~/.local/share/opencode/log/opencode.log | tail -3   # solo entradas previas a P5
# 6.4 tokens/modelos
curl -s http://localhost:11434/v1/models | python3 -c "import json,sys; print(len(json.load(sys.stdin)['data']))"
curl -s http://localhost:11435/health
# 6.5 web
curl -s -o /dev/null -w "%{http_code}" http://localhost:8081/
```

## 7. Criterios de cierre

Todos los mínimos del §5 verificados con salida real, backup restaurable, log sin nuevos errores C1-C3, y sesión web/run operativa con 2 modelos (qwen2.5-coder:32b y qwen3:32b-q8_0).

## 8. Pendientes / fuera de alcance

- Investigar POR QUÉ el rootfs volvió a `ro` pese al fix documentado de 2026-07-19 (posible crash previo / fsck / fstab no aplicado en este arranque) — TASK aparte.
- MCP: si Ramón quiere MCP de gateway futuro, validar el paquete ANTES de añadirlo a la config.
- La Web sigue funcionando con `deepseek-v4-flash-free` (gratis, OK) para el coordinador mientras tanto.

---

## 9. ANÁLISIS DEL PLAN (v2, 2026-08-17, WEB — reflexión tras experimentos)

### Puntos buenos
1. Estructura completa (contexto→diagnóstico→acciones→mínimos→validación→cierre) con riesgo y reversibilidad por paso.
2. C1/C2/C3 correctos y con evidencia de log/`ollama show` (MCP fantasma 404, reasoning en modelos sin thinking, deepseek-v4-pro sin saldo).
3. Separación de responsabilidades: sudo al humano, edición al WEB, sin romper ramas 027/029 ni archivos ajenos.
4. Backup previo (P2) y "NO hacer" explícito.

### Puntos malos
1. **C4 (rootfs RO como causa de que `opencode run` no ejecute tools) REFUTADA por experimento**: con `XDG_STATE_HOME=/tmp/opencode/state-test` (RW) y `--auto`, `opencode run --model ollama/qwen2.5-coder:32b` SIGUE sin ejecutar la tool (imprime el JSON crudo). El bloqueo EROFS de locks (real, run 54cbe1f1 18:59) afecta al almacenamiento de estado, pero NO explica el no-ejecutar tools.
2. **El experimento con `deepseek-r1:14b` revela un problema NO contemplado**: `400 exceeded context size (8192)` — opencode envía ~25.2k tokens (AGENTS.md gigante + contexto) y los modelos locales corren con `n_ctx=8192`. Los modelos locales quizá NO PUEDEN funcionar con el system prompt actual sin subir `num_ctx`.
3. **Contradicción no investigada**: `/etc/fstab` dice `rw,` (con coma rara) y `/proc/cmdline` contiene tanto `ro` como `rw`... y aun así `/` está `ro`. El plan pide remontar sin explicar por qué está ro (¿fsck.mode=force, remount por hardening lanzado tras el boot, o mount inicial del initramfs?). Riesgo: se vuelve a ro tras reinicio.
4. **Namespace no verificado**: mi bash corre en `mnt:[4026533149]` (≠ host `4026531832`); parte de lo visto en RO puede ser de mi namespace. El plan no pide confirmar el estado REAL del host (regla v1.6) antes del remount con sudo.
5. **El síntoma principal se reproduce en ASUS con 2 modelos distintos (qwen2.5-coder:32b y deepseek-r1:14b)**, lo que apunta a opencode+provider+config (y n_ctx), no a un modelo concreto ni al disco.

### Mejoras (propuestas concretas)
1. (obligatorio) **Añadir Fase 0b de diagnóstico aislado, SIN sudo**: reproducir con `qwen3:32b-q8_0` (único local con tools+thinking fiable) y con `--auto`; si tampoco ejecuta → causa es provider/parseo/n_ctx, no rootfs, y la Fase 1 (remount) queda como mejora de estado, no como solución al síntoma.
2. (obligatorio) **Añadir bloque n_ctx**: `ollama set <modelo> num_ctx 32768` para los 2-3 modelos de trabajo y/o recortar el system prompt (AGENTS.md es ~25k tokens); validar que el run ya no da `400 exceeded context size`.
3. (importante) **Confirmar host antes de remount**: pedir a Ramón `grep " / " /proc/mounts` y `readlink /proc/self/ns/mnt` en el HOST (no en mi namespace) antes de P1.
4. (importante) **Aislar variables**: hacer el remount rw SOLO como experimento (una sesión) y re-testear run SIN tocar todavía la config; si sigue fallando, C4 queda descartada como causa del síntoma y la config (C1-C3) pasa a ser la hipótesis principal.
5. (mejora) Criterio de cierre más realista: exigir que `qwen3:32b-q8_0` (no qwen2.5-coder:32b, que falla) ejecute una tool con `--auto` tras subir `num_ctx`.
6. (mejora) Definir qué significa "OpenCode escritorio" (¿web 8081 de ASUS? ¿app de la Mac?), porque el TERM usa otra instalación (Mac) y el plan solo cubre ASUS.

### Veredicto: GO CON CAMBIOS
C1/C2/C3 (config, MCP, saldo) están bien y deben ejecutarse; pero la hipótesis C4 como causa principal del síntoma está refutada por experimento, y falta el bloque 6 n_ctx + confirmación de host. Ejecutar solo tras añadir Fase 0b y bloque n_ctx.

---

## 10. EJECUCIÓN REAL (2026-08-17 ~21:37-22:10, RAMÓN + WEB) — hallazgos definitivos

### Cambios ya aplicados por RAMÓN (verificados por WEB el 21:45)
1. `OLLAMA_CONTEXT_LENGTH=32768` en `/etc/systemd/system/ollama.service.d/override.conf` — VERIFICADO `systemctl show ollama.service --property=Environment`.
2. Config `~/.config/opencode/opencode.json` limpiada: **sin** `mcp.openclaw`, `reasoning: true` solo en `deepseek-r1:14b` y `qwen3:32b-q8_0`, default = `ollama/qwen3:32b-q8_0` — VERIFICADO (lectura directa, 64 líneas).
3. `opencode.service` reiniciado — VERIFICADO `ExecMainStartTimestamp=Mon 2026-08-17 21:37:52 CEST`.

### Pruebas de ejecución de herramientas (B, 21:50-22:10, con `--auto` y XDG dirs en /tmp RW)

| Modelo | ¿Emite tool call? | ¿EJECUTA bash? | Comportamiento observado |
|--------|-------------------|----------------|--------------------------|
| `ollama/qwen3:32b-q8_0` | Sí (JSON en texto) | **NO** | Responde con texto que imita el formato de reporte del AGENTS.md (alucinación del system prompt), no ejecuta la tool. Con `--print-logs`: stream OK, sin ejecución. |
| `ollama/deepseek-r1:14b` | No visible | **NO** | **ALUCINA la salida**: devuelve un `ls -la` falso (fechas 2023, otro directorio) sin ejecutar nada. |
| `ollama/qwen2.5-coder:32b` | Sí (JSON en texto) | **NO** | Entra en **bucle infinito** repitiendo `{"name": "bash", ...}` como texto plano (8+ iteraciones, timeout 400s). |

### Conclusión C4 (rootfs RO) — DESCARTADA como causa del síntoma
Reproducción con `XDG_STATE_HOME=/tmp/opencode/state2`, `XDG_CACHE_HOME=/tmp/opencode/cache2`, `XDG_DATA_HOME=/tmp/opencode/data2` (todo RW): **mismo fallo**. El bloqueo EROFS de locks/snapshot es real pero NO impide la ejecución de tools; es un problema secundario (falla al escribir modelos.json del caché).

### Diagnóstico final (v2)
- **Causa raíz del síntoma**: el runtime `ai-sdk` de opencode v1.18.18 con el provider `@ai-sdk/openai-compatible` (Ollama /v1) NO materializa las tool calls de los modelos locales: los 3 modelos emiten tool call en el flujo, pero opencode la imprime como texto y sigue el loop sin ejecutar. No es el modelo (los 3 fallan), no es n_ctx (32768 OK, sin error 400), no es la config (limpia), no es el disco (RW en /tmp tampoco).
- El error `Failed to fetch models.dev ... EROFS` persiste (rootfs RO) pero es cosmético.

### Decisión D/E
- **Ningún modelo local ejecuta herramientas → OpenCode local (CLI `opencode run`) NO es utilizable para tareas con herramientas en esta versión (v1.18.18 + ai-sdk/openai-compatible + Ollama).**
- **Alternativa viable propuesta**: usar **OpenCode Web** (que funciona con `deepseek-v4-flash-free` / provider nube) para tareas con herramientas, y **terminal manual** para el resto. Mientras tanto, investigar el bug del adapter ai-sdk (posible downgrade a v1.18.x anterior, o probar provider `ollama` nativo en vez de `openai-compatible`).
- Pendiente: NINGUNA acción de config adicional por parte del WEB; solo investigación upstream (bug del provider) — TASK propuesta.

### Estado del plan
- P1 (remount rw): **SIGUE PENDIENTE** — necesario para arreglar el error EROFS de caché/snapshot, pero NO arregla el síntoma de tools. Recomendado: aplicar igualmente (mejora de robustez).
- P3 (config): **YA APLICADO** por Ramón.
- P5 (restart servicio): **YA APLICADO** por Ramón.
- P4 (deepseek-v4-pro saldo): **PENDIENTE decisión humana** (recargar o eliminar; la Web funciona con flash-free).
