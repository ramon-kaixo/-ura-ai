# Config Map Audit — 2026-07-26
# SOLO DIAGNÓSTICO. Sin refactorización.

## Hallazgos

### 1. RUTAS_CONFIG_OPENCODE — Duplicado 6 veces 🔴

| Archivo | Línea | Valor |
|---------|-------|-------|
| motor/core/config.py | 102 | ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"] |
| motor/diagnostico/__init__.py | 19 | ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"] |
| motor/diagnostico/diagnostico.py | 24 | ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"] |
| motor/scanner/__init__.py | 24 | ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"] |
| motor/scanner/scanner.py | 30 | ["/etc/opencode/opencode.jsonc", "/etc/opencode/opencode.json"] |

**Problema:** Mismo array hardcodeado en 5 archivos. Cambiar una ruta requiere editar 5 archivos.

**Fix futuro:** Mover a  o  como fuente única.

---

### 2. URA_ROOT — 30+ definiciones, 6 patrones distintos 🔴

| Patrón | Archivos | Ejemplo |
|--------|----------|---------|
|  | 15+ | core/agents/constants.py, core/ura_multi_agent.py |
|  | 5 | scripts/pro/refactor_large_functions.py, sandbox_industrial.py |
|  | 4 | scripts/pro/arq_auditor.py, arq_checker.py |
|  | 2 | scripts/pro/bypass_linksys_gui.py, motor/brain/executor.py |
|  | 1 | scripts/pro/tuneladora/config.py |
| Hardcodeado  | 5 | scripts/pro/auto_reglas.py, scanner_autoajuste.py |

**Problema:** Si el repo se mueve a otra ruta o usuario, 30+ archivos rompen.

**Fix futuro:** UN solo  en , todos los demás importan desde ahí.

---

### 3. CONFIG_PATH — 9 archivos, 6 configs distintas 🟡

| Archivo | Config apuntada |
|---------|-----------------|
| core/config_manager.py | config/system_config.json |
| core/error_sandbox.py | config/error_sandbox.json |
| core/guardian_disco.py | .nervioso/guardian_config.json |
| core/debate/debate_engine.py | core/debate/committee_config.json |
| monitor/snc.py | config/system_config.json |
| scripts/pro/chunk_optimizer.py | .nervioso/chunk_config.json |
| scripts/pro/reglas_applier.py | config/reglas_builtin.json |
| scripts/pro/reglas_loader.py | config/reglas_builtin.json |
| scripts/pro/reglas_generator.py | config/reglas_builtin.json |

**Problema:** Cada módulo define su propio CONFIG_PATH. No hay centralización.

**Fix futuro:**  con funciones tipo , .

---

### 4. Archivos de config dispersos — 50+ JSON/TOML/YAML 🟡

Ubicaciones:
-  — 6 archivos (system, dispositivos, infra, reglas, schema, settings)
-  — 5+ archivos (chunk_config, guardian_config, hashes, etc.)
-  — 1 archivo (committee_config.json)
-  — 4+ archivos (manifest, emergency_runbook, estado_alemania, lildax)
-  — 15+ archivos (benchmarks, baselines)
- Raíz — docker-compose.yml, pyproject.toml, prometheus.yml

**Problema:** No hay convención de dónde va qué tipo de config.

---

### 5. DOTENV — Inconsistente 🟡

-  carga  vía 
- Pero los secretos reales están en 
- No hay  en la raíz del repo

**Problema:** Doble sistema de secretos.  puede cargar valores incorrectos si existe un  viejo.

---

### 6. URA_HOME vs URA_ROOT 🟢

-  en 
-  apunta a  en todos los demás

**Problema:** Naming inconsistente.  debería llamarse  o viceversa.

---

## Recomendaciones (futuro)

### Corto plazo
1. **Centralizar RUTAS_CONFIG_OPENCODE** en , eliminar de los otros 4 archivos
2. **Centralizar URA_ROOT** en un solo módulo 
3. **Documentar convención de config:**  → estática,  → runtime,  → infra

### Medio plazo
4. **Crear ** con loader unificado para todos los JSON
5. **Eliminar ** de mochila_server.py, usar solo 
6. **Estandarizar nombres:**  para repo,  para directorio padre

### Largo plazo
7. **Mover todo a ** — un solo modelo de config con validación
