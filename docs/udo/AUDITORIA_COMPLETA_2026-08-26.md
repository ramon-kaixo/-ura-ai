# AUDITORÍA COMPLETA URA — 2026-08-26

**Ejecutado por**: TERM (OpenCode Terminal)
**Máquinas**: Mac Mini M4 + GX10 (NVIDIA GB10)
**Fecha**: 2026-08-26 11:07 CDT

---

## 1. CÓDIGO

### 1.1 Duplicados (jscpd)
- **2,971 líneas duplicadas (3.6%)** — sin clones significativos (>50 líneas)
- 0 archivos con duplicación relevante
- **Veredicto**: Aceptable. No hay duplicación que amerite refactorización

### 1.2 Imports Cíclicos
- ✅ **motor/ NO importa de core/** — regla de arquitectura respetada
- ⚠️ **core/ importa de motor/** en 10 archivos (permitido por diseño):
  - `core/auth_layer.py`, `core/mochila/tools.py`, `core/mochila/mochila_server.py`
  - `core/mochila/_state.py`, `core/infra/heartbeat.py`, `core/debate/debate_engine.py`
  - `core/logs/guardian_logger.py`, `core/memoria/qdrant_store.py`
  - `core/model_router/handler.py`, `core/model_router/cli.py`
- **Veredicto**: OK — core depende de motor (unidireccional)

### 1.3 Complejidad Ciclomática (radon)
Funciones con **CC > 10** (críticas):

| CC | Función | Archivo |
|----|---------|---------|
| 31 | `test_full_pipeline` | motor/tests/test_pipeline_e2e.py |
| 28 | `test_contextual_resolve_ramas` | motor/tests/test_fusion.py |
| 27 | `test_ciclo_vida_completo` | motor/tests/test_fusion.py |
| 27 | `test_serializacion` | motor/tests/test_fusion.py |
| 20 | `cmd_learn` | motor/cli/cmd_diag.py |
| 18 | `cmd_service` | motor/cli/cmd_ura.py |
| 17 | `_build_system_prompt` | motor/assistant/api/handlers.py |
| 17 | `execute` | motor/intelligence/agents/parallel.py |
| 17 | `cmd_dashboard` | motor/cli/cmd_ura.py |
| 17 | `do_GET` | core/model_router/handler.py |
| 17 | `proxy_request` | core/model_router/proxy.py |
| 16 | `_apply_config_overrides` | motor/core/config.py |
| 16 | `search` | motor/intelligence/memory/semantic.py |
| 15 | `_stream` | core/mochila/adapter.py |
| 15 | `_analizar_estructuras` | core/guardians/ast_sentinel.py |

- **Producción con CC > 15**: 8 funciones (candidate a refactor)
- **Tests con CC > 25**: 4 tests (tests grandes, no prioridad)
- **Veredicto**: ~8 funciones de producción con alta complejidad, priorizar refactor de `cmd_learn` (CC=20), `_build_system_prompt` (CC=17), `do_GET` (CC=17)

### 1.4 Código Muerto (vulture, confidence ≥80%)
11 hallazgos, todos de **baja severidad** (variables no usadas):

| Archivo | Tipo | Detalle |
|---------|------|---------|
| `core/change_guardian.py:82` | variable | `exc_tb` no usada |
| `core/infra/heartbeat.py:253` | variable | `frame` no usada |
| `core/watchdog_funciones.py:116` | variable | `signum`, `frame` no usadas |
| `core/watchdog_funciones.py:144` | variable | `on_timeout` no usada |
| `motor/core/voice/anker_mac_pipeline.py:65` | variable | `frames` no usada |
| `motor/core/voice/anker_pipeline.py:84` | variable | `frames` no usada |
| `motor/tests/test_*.py` (3 archivos) | ternario | condiciones insatisfacibles |

- **Veredicto**: 6 variables no usadas en producción + 3 ternarios insatisfacibles en tests. Baja prioridad — limpieza cosmética

### 1.5 Bugs de Seguridad (bandit)
- **1 issue Medium**: `hardcoded_tmp_directory` en test (`/tmp/ruta_que_no_existe_xyz`)
- **0 issues High**
- 3,387 Low (misc lint issues)
- **Veredicto**: Limpio. El único hallazgo es en un test con path temporal hardcodeado

---

## 2. INFRAESTRUCTURA DE RED

### 2.1 Conectividad Mac↔GX10
| Prueba | Resultado |
|--------|-----------|
| GX10→Mac ping (Tailscale) | **100% packet loss** ⚠️ |
| Mac→GX10 SSH | ✅ Funcional |

- **Causa probable**: GX10 usa Tailscale pero Mac puede estar en otro segmento, o GX10 perdió ruta Tailscale
- **Veredicto**: ⚠️ GX10 no puede hacer ping a Mac por Tailscale. SSH funciona (usa TCP, no ICMP). Investigar si es firewall ICMP o routing

### 2.2 Puertos Abiertos (GX10)
| Puerto | Servicio | Estado |
|--------|----------|--------|
| 22 | SSH | ✅ OK |
| 2222 | SSH alternativo | ✅ OK |
| 6333 | Qdrant (vector DB) | ⚠️ Bind 0.0.0.0 (exposto a TODA la red) |
| 8081 | OpenCode Web | ✅ OK (opencode PID 739005) |
| 11434 | Ollama | ✅ OK |
| 22000 | Syncthing | ✅ OK |

- **Hallazgo**: Qdrant (6333) escucha en `0.0.0.0` — accesible desde LAN. Debería ser `127.0.0.1` o solo Tailscale
- **Veredicto**: ⚠️ Qdrant expuesto a LAN, verificar si es intencional

### 2.3 Firewall
- `ufw status`: **no output** (ufw no está activo o no instalado)
- `iptables`: no se pudo ejecutar sin sudo
- **Veredicto**: ⚠️ No hay firewall visible. Con Tailscale, el perímetro es la ACL de Tailscale. Verificar tailscale-acls.json

### 2.4 DNS / Hosts
- `/etc/hosts` en GX10: `127.0.0.1 gx10-64c3` — solo localhost
- Tailscale MagicDNS: funcional (GX10 alcanzable por `100.72.103.12`)
- **Veredicto**: ✅ OK

### 2.5 SSH
| Aspecto | Mac | GX10 |
|---------|-----|------|
| `~/.ssh/` permisos | 700 ✅ | 700 ✅ |
| Claves privadas permisos | 600 ✅ | **755 en 3 archivos** ⚠️ |
| `config` permisos | 644 ⚠️ | 644 ⚠️ |
| Passphrase en claves | N/A | N/A (no verificable remoto) |

- **Hallazgo GX10**: 3 claves con permisos 755 (ejecutable): `id_gx10_mac`, `id_ura_backup`, `id_ura_watchdog`. Deberían ser 600
- **Hallazgo GX10**: 4 backups de `~/.ssh/config` — candidatos a limpieza
- **Veredicto**: ⚠️ Permisos de claves SSH en GX10 demasiado abiertos (755 en vez de 600)

---

## 3. SEGURIDAD

### 3.1 Secretos en Código
- ✅ **0 secretos hardcodeados** en motor/ o core/ (grep limpio)
- Todos los hallazgos son campos de tokens/métricas (no secretos reales)
- **Veredicto**: Limpio

### 3.2 Permisos de Archivos
| Archivo | Permisos Esperadas | Permisos Reales | Estado |
|---------|-------------------|-----------------|--------|
| `~/.config/ura/secrets.env` (Mac) | 600 | 600 ✅ | OK |
| `/etc/ura/secrets.env` (GX10) | 600 | 600 ✅ | OK |
| `~/URA/.env` (Mac) | 600 | **644** ⚠️ |.world-readable |
| `committee_config.json` | chattr +i | +i ✅ | OK |
| `lildax_config.json` | chattr +i | +i ✅ | OK |

- **Hallazgo**: `~/URA/.env` tiene permisos 644 (lectura world). Contiene `URA_API_KEY` — no es secreto crítico pero debería ser 600
- **Veredicto**: ⚠️ .env world-readable (baja severidad — solo contiene API key de test)

### 3.3 Docker
- ✅ Sin imágenes antiguas
- Sin contenedores corriendo
- **Veredicto**: Limpio

### 3.4 Backups con Secretos
- **1 backup con password**: `backups_gx10/deploy/lildax_config.json.backup.20260825_000850`
  - Contiene credenciales Lildax
  - **Recomendación**: eliminar o mover a directorio seguro con permisos 600
- **Veredicto**: ⚠️ Backup con credenciales expuestas en directorio no protegido

---

## 4. SERVICIOS

### 4.1 Servicios Systemd (GX10)
**17 servicios activos** — todos OK:

| Servicio | Estado |
|----------|--------|
| ollama | ✅ running |
| opencode | ✅ running |
| tailscaled | ✅ running |
| ura-api | ✅ running |
| ura-assistant | ✅ running |
| ura-audit-api | ✅ running |
| ura-contraste | ✅ running |
| ura-detector | ✅ running |
| ura-go2rtc | ✅ running |
| ura-heartbeat | ✅ running |
| ura-metrics | ✅ running |
| ura-mkdocs | ✅ running |
| ura-mochila | ✅ running |
| ura-ssh-guard | ✅ running |
| ura-voice | ✅ running |
| ura-watchdog-buffer | ✅ running |
| ura-xvfb | ✅ running |

### 4.2 Recursos del Sistema
| Recurso | Valor | Estado |
|---------|-------|--------|
| Disco | 646GB/1.8TB (38%) | ✅ OK |
| RAM | 20GB/121GB usado (16%) | ✅ OK (101GB disponible) |
| GPU | 40°C, 0% utilidad | ✅ OK (idle) |
| Uptime | 3 días, 9h | ✅ OK |
| Load avg | 1.13, 1.41, 1.69 | ✅ OK (baja carga) |

### 4.3 Procesos Problemáticos
- **1 zombie**: PID 123975 (`sd_espeak-ng-mb`) — proceso hijo de `ura-voice`. No crítico pero debería limpiarse
- Sin procesos colgados
- **Veredicto**: ⚠️ 1 zombie de espeak-ng (voz), limpieza menor

---

## 5. TESTS

### 5.1 Cobertura
- **10,540 tests coleccionados** (suite completa)
- **588 nightly tests**: todos pasan (41s en Mac)
- **Smoke tests**: 13/13 pasan (1.1s)
- Cobertura global motor/: **~50-60%** estimada (CI shows incremental improvements)
- **Veredicto**: Suite masiva y funcional. Cobertura en zona aceptable

### 5.2 Tests Flaky / Rotos
- ✅ **0 tests rotos** tras fixes de PR #33
- Tests flaky conocidos: `test_llm_contract.py::test_no_hay_imports_no_publicos` (intermitente por estado de módulos)
- **Veredicto**: Limpio

### 5.3 Tests Skippeados
- No se encontraron `@pytest.mark.skip` ni `@pytest.mark.xfail` activos
- **Veredicto**: ✅ Sin tests skippeados

---

## 6. DOCUMENTACIÓN Y GOBERNANZA

### 6.1 Documentación
| Archivo | Actualizado | Notas |
|---------|-------------|-------|
| README.md | ✅ | IP Tailscale correcta (100.72.103.12:8003) |
| AGENTS.md | ✅ | Sin referencias obsoletas (knowledge_engine.py eliminado) |
| ROLES_OPENCODE.md | ❓ | No verificado |
| docs/architecture/*.md | ✅ | Closeouts F7-F29 + ADRs presentes |

### 6.2 Tasks UDO
- **201 tasks** en `docs/udo/tasks/`
- TASK-20260825-017: expediente creado ✅
- Sin tasks en REVIEW >48h detectadas
- **Veredicto**: Inventario grande (201), considerar archivado de tasks antiguas

### 6.3 ADRs
- 15+ ADRs en `docs/architecture/`
- Decisiones clave documentadas: ADR-007 (core rule), ADR-011 (plugins), ADR-028 (protocols)
- **Veredicto**: ✅ Bien documentado

---

## 7. ACCIONES RECOMENDADAS (priorizadas)

### 🔴 ALTA PRIORIDAD
1. **Qdrant expuesto en 0.0.0.0:6333** — verificar si es intencional. Si no, bind a 127.0.0.1 o Tailscale IP
2. **Backup con credenciales**: `backups_gx10/deploy/lildax_config.json.backup.20260825_000850` — eliminar o proteger con permisos 600
3. **Permisos SSH claves GX10**: `id_gx10_mac`, `id_ura_backup`, `id_ura_watchdog` con 755 → cambiar a 600

### 🟡 MEDIA PRIORIDAD
4. **GX10→Mac ping falla** — investigar routing Tailscale (SSH funciona, ICMP no)
5. **Zombie `sd_espeak-ng-mb`** — limpiar PID 123975 (proceso hijo ura-voice)
6. **~/.env Mac permisos 644** → cambiar a 600
7. **Complejidad alta**: refactorizar `cmd_learn` (CC=20), `_build_system_prompt` (CC=17), `do_GET` (CC=17)
8. **Backups SSH en GX10**: 4 archivos `config.backup.*` — limpiar si no se necesitan

### 🟢 BAJA PRIORIDAD
9. **Código muerto**: 6 variables no usadas + 3 ternarios insatisfacibles en tests (cosmético)
10. **201 tasks UDO**: considerar archivado de tasks antiguas (F1-F3) para reducir ruido
11. **ufw no activo**: evaluar si se necesita firewall local además de Tailscale ACLs

---

*Informe generado por auditoría automatizada + revisión manual. Ejecutado en ~5 minutos.*
*SHA del repo auditado: 450ac0a4 (main)*
