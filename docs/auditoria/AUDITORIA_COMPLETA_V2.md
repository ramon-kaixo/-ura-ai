# Auditoría Completa URA — Checkpoint V2

**Fecha:** 2026-05-03  
**Alcance:** 428 archivos Python, 121 módulos en `core/`, 54 tests, ~32k LOC.  
**Resultado tests:** **411 passed / 5 skipped / 0 failed** (skipped = platform-specific Windows/Linux).

---

## 🔴 PROBLEMAS CRÍTICOS ENCONTRADOS Y ARREGLADOS

### 1. Secretos filtrados en git (MÁXIMA PRIORIDAD) 🚨

**Archivos con credenciales REALES commiteadas en git:**

| Archivo | Contenido |
|---|---|
| `config/gmail_credentials.json` | access_token + refresh_token + client_secret de Google OAuth |
| `config/gmail_token.json` | token OAuth + refresh_token |
| `.boveda_key` | clave maestra de bóveda (44 bytes) |
| `credentials.json` | credenciales Google |
| `token.pickle` | token OAuth serializado |

**Acción ejecutada:**
- Añadidos al `.gitignore`
- Removidos del tracking git con `git rm --cached` (archivos locales preservados)
- Patrones globales añadidos: `*.pem`, `*.key`, `secrets/`, `oauth_*.json`, `service_account*.json`

**⚠️ ACCIÓN REQUERIDA POR EL USUARIO (NO AUTOMATIZABLE):**

1. **ROTAR INMEDIATAMENTE** todas las credenciales Google OAuth comprometidas:
   - Revocar tokens en https://myaccount.google.com/permissions
   - Generar nuevas credenciales en Google Cloud Console
2. **Rotar la `.boveda_key`** (si fue alguna vez pusheada a un remoto)
3. **Limpiar la historia de git** si el repo es público o fue compartido:
   ```bash
   # OPCIÓN A: BFG Repo-Cleaner (recomendado)
   brew install bfg
   bfg --delete-files gmail_credentials.json
   bfg --delete-files gmail_token.json
   bfg --delete-files .boveda_key
   bfg --delete-files credentials.json
   bfg --delete-files token.pickle
   git reflog expire --expire=now --all && git gc --prune=now --aggressive
   git push --force
   ```
4. Hacer commit + push del `.gitignore` actualizado

### 2. `shell=True` en 3 ejecutores de código (vulnerabilidad CWE-78) 🚨

| Archivo | Ubicación | Fix aplicado |
|---|---|---|
| `core/ejecutor_seguro.py:63` | Ejecutor de comandos "seguro" (irónico) | `shlex.split()` + `shell=False` |
| `core/memory_manager.py:280` | Arranque de servicios brew | `shlex.split()` + `shell=False` |
| `core/ura_tools_interaction.py:119` | API de herramientas | `shlex.split()` + `shell=False` + validación de args vacíos |

### 3. `exec()` in-process para código Python del usuario 🚨

**Archivo:** `core/ura_tools_interaction.py:181`  
**Problema:** `exec(code, {})` podía contaminar el proceso en ejecución, leer variables, etc.  
**Fix:** Reemplazado por `subprocess.run([sys.executable, "-I", "-c", code])` — ejecución aislada + timeout 30s + flag `-I` (isolated mode, ignora `PYTHONPATH` y site packages del usuario).

### 4. Imports rotos a módulos inexistentes

| Módulo | Import roto | Fix |
|---|---|---|
| `core/tecnico_ejecutor.py` | `from core.test_forzado` | Movido `tests/test_forzado.py` → `core/test_forzado.py` (era código de dominio mal ubicado, pytest lo intentaba recolectar como test class por el prefijo `Test`) |
| `core/coordinador_verificacion.py` | dependía del anterior | Resuelto por transitividad |
| `core/scheduler_buscadores.py` | `from core.database`, `from core.lock_manager` | Import opcional con degradación graceful + guards de uso |
| `core/self_healing_system.py` | `from evolutionary_system` | Import opcional + guards en `run_weekly_benchmarks` |

**Resultado:** de **7 módulos core con ImportError** a **0/121 módulos con errores de import**.

### 5. Archivo basura en root

`=5.15.0` — output accidental de `pip install >= 5.15.0` capturado como archivo. Eliminado.

### 6. TODOs CRÍTICOS en `main_final.py` sin resolver

**3 TODOs idénticos** avisaban de una fuga de threads en `closeEvent`:

```
# TODO CRÍTICO: añadir este thread al cleanup de closeEvent
# Ver URA_CHANGELOG.md sección PENDIENTES — HACER ANTES DE PRODUCCIÓN
```

Afectaba a:
- `voice_recognizer` (VoiceRecognitionThread)
- `tts_engine` (TextToSpeechThread)
- `continuous_conversation` (ContinuousVoiceConversationThread)

**Fix:** Añadido loop de cleanup robusto en `closeEvent()` que llama `.stop()`, `.quit()`, `.wait(5000)` con try/except por thread.

### 7. Lint: 5 errores `F541` (f-string sin placeholders)

Corregidos automáticamente con `ruff check --fix`.

---

## 🟡 DEPENDENCIA VULNERABLE

`pip 26.0.1` → **CVE-2026-3219**. Fix: `pip install --upgrade pip` (usuario decide).

---

## 🟢 RESUMEN DE MÉTRICAS

| Métrica | Antes | Después |
|---|---|---|
| Ruff errors | 5 | **0** |
| Bandit HIGH severity | 3 | **0** |
| Bandit MEDIUM severity | 2 | **0** (`exec()` eliminado) |
| ImportError en `core/` | 7 / 120 | **0 / 121** |
| Tests passed | 410 | **411** |
| Tests failed | 1 | **0** |
| Secretos en git | 5 archivos | **0 tracked** (local preservado) |
| TODOs CRÍTICOS | 3 | **0** |
| Archivos basura root | 1 (`=5.15.0`) | **0** |

---

## 💡 SUGERENCIAS DE MEJORA (NO APLICADAS — REQUIEREN DECISIÓN)

### Arquitectura

1. **Root del proyecto sobrecargado**: >100 archivos en la raíz (scripts `.sh`, markdowns de auditoría previa, configs). Sugerencia:
   - Mover docs a `docs/` (ya existe pero vacía)
   - Mover scripts `.sh` a `scripts/` (ya existe)
   - Consolidar los 15+ `.md` de auditoría/status en `docs/audits/`

2. **`main_final.py` tiene 3102 líneas** → God object. Plan de refactor:
   - Extraer `MainWindow` → `ui/main_window.py`
   - Extraer lógica de voz → `ui/voice_controller.py`
   - Extraer gestión de threads de mensajería → `ui/messaging_controller.py`

3. **2 entornos virtuales** (`venv/` y `.venv/`) — consolidar en uno.

4. **Dos archivos `requirements`** (`requirements.txt` + `requirements.legacy.txt`) — auditar qué versiones realmente se usan y borrar el legacy.

### Calidad de código

5. **33 `DeprecationWarning`** por `datetime.utcnow()`. Reemplazar por `datetime.now(datetime.UTC)` en:
   - `core/vector_database.py:30`
   - `core/semantic_search.py:39`
   - `core/semantic_memory.py:57`
   - Otros 30 ocurrencias.

6. **240 issues LOW de bandit** — mayoría son `try/except/pass` y `subprocess` sin shell=True (falsos positivos). Revisar y marcar con `# nosec` donde aplique.

7. **3 TODOs restantes** (no críticos):
   - `scripts/ura_auto_sync.py:320` — integración dashboard
   - `api/main.py:52` — validación real de API key
   - `api/main.py:129` — check real de Ollama

### Seguridad

8. **Crear script de verificación pre-commit** con `bandit -ll` + `pip-audit` + `ruff check` + `pytest -x` (ya existe `.pre-commit-config.yaml`, verificar que corra estos).

9. **Añadir CI/CD**: `.github/workflows/` existe — verificar que ejecute la suite completa + security scanners en cada PR.

10. **Auditar `core/code_agents/`** (subpaquete con `# nosec` en SQL) — asegurar que las cadenas SQL sean siempre parametrizadas, no concatenadas.

### Dependencias opcionales

11. El proyecto tiene muchas dependencias opcionales con try/except (langchain, scikit-learn, playwright, ollama, google-auth, redis). Sugerencia: documentar en README la matriz de features → dependencias para que el usuario sepa qué instalar según su caso de uso.

12. **`setup.py` + `pyproject.toml` coexisten** — migrar completamente a `pyproject.toml` (setup.py deprecated).

### Tests

13. **5 tests platform-specific** (Windows/Linux en macOS) — mover a un marcador `@pytest.mark.platform_specific` y excluir por default con `pytest -m 'not platform_specific'`.

14. **Cobertura** — ejecutar `pytest --cov=core --cov-report=html` y apuntar a 80%+ de cobertura en `core/`.

---

## ✅ ARCHIVOS MODIFICADOS EN ESTA AUDITORÍA

| Archivo | Cambio |
|---|---|
| `.gitignore` | +11 líneas (credenciales + glob `=*`) |
| `core/ejecutor_seguro.py` | shell=True → shlex.split |
| `core/memory_manager.py` | shell=True → shlex.split |
| `core/ura_tools_interaction.py` | shell=True + exec() → subprocess aislado |
| `core/scheduler_buscadores.py` | imports opcionales + guards |
| `core/self_healing_system.py` | evolutionary_system opcional + guards |
| `core/test_forzado.py` | **nuevo** (movido desde `tests/`) |
| `tests/test_forzado.py` | **eliminado** (reubicado) |
| `main_final.py` | cleanup voice threads + TODOs resueltos |
| `tests/test_integration_awareness.py` | actualizado a API subprocess |
| `=5.15.0` | eliminado |
| Varios (ruff --fix) | 5 f-strings sin placeholders |

**Archivos removidos de git tracking (preservados localmente):**
- `.boveda_key`
- `credentials.json`
- `token.pickle`
- `config/gmail_credentials.json`
- `config/gmail_token.json`
