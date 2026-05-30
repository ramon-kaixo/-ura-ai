# Code Review — OpenCode Manual — 2026-05-13
## 50 bugs encontrados en 27 archivos

---

## CRASH / Runtime Error (15)

### 1. `core/health_monitor.py:85,91`
**NameError**: `downtenance` → `downtime`
```diff
- self.logger.info(f"Health Alert: {downtenance / 60:.1f} min downtime")
+ self.logger.info(f"Health Alert: {downtime / 60:.1f} min downtime")
```

### 2. `core/ura_anticipation.py:191`
**ValueError**: `int("14:00")` falla por los dos puntos
```diff
- pattern_hour = int(pattern.pattern_value)
+ pattern_hour = int(pattern.pattern_value.split(":")[0])
```

### 3. `core/agente_maestro.py:373`
**AttributeError**: `estado()` no existe, es `estado_sistema()`
```diff
- print(maestro.estado())
+ print(maestro.estado_sistema())
```

### 4. `core/security/hermetic_states.py:16`
**ImportError** en Python <3.11: `StrEnum` no existe
```diff
- from enum import Enum, StrEnum
+ from enum import Enum
+ class HermeticState(str, Enum):
```

### 5. `core/buscadores/buscador_documentacion.py:7`
**ImportError** en Python <3.11: `datetime.UTC` no existe
```diff
- from datetime import datetime, timezone, UTC
+ from datetime import datetime, timezone
+ # usar timezone.utc en vez de UTC
```

### 6. `agents/agente_verificador_tareas.py:73`
**TypeError** en Python <3.8: `unlink(missing_ok=...)` no soportado
```diff
- VERIFIER_PID.unlink(missing_ok=True)
+ try:
+     VERIFIER_PID.unlink()
+ except FileNotFoundError:
+     pass
```

### 7. `core/sandbox.py:127`
**AttributeError**: `spec.loader` puede ser `None` (namespace packages)
```diff
- spec.loader.exec_module(module)
+ if spec.loader is not None:
+     spec.loader.exec_module(module)
+ else:
+     return False
```

### 8. `core/sandbox_orchestrator.py:120-126`
**TypeError**: `_load_log()` puede devolver dict, pero se espera lista
```diff
- self.log[-500:]
+ data = json.load(f)
+ return data if isinstance(data, list) else []
```

### 9. `core/search_cache.py:36`
**PermissionError**: Toshiba no montada → intenta crear en `/Volumes/`
```diff
+ if not self.cache_file.parent.exists():
+     try:
+         self.cache_file.parent.mkdir(parents=True, exist_ok=True)
+     except PermissionError:
+         self.cache_file = Path.home() / ".ura" / "cache" / "search_cache.json"
+         self.cache_file.parent.mkdir(parents=True, exist_ok=True)
```

### 10. `core/toshiba_backup.py:29`
**PermissionError**: mismo patrón que arriba
```diff
+ if not is_toshiba_mounted():
+     raise RuntimeError("Toshiba no disponible")
  self.backup_dir.mkdir(parents=True, exist_ok=True)
```

### 11. `core/lector_documentacion.py:65`
**RuntimeError**: `asyncio.run()` dentro de un event loop existente
```diff
- result = asyncio.run(self.search_orchestrator.search(query))
+ try:
+     loop = asyncio.get_running_loop()
+ except RuntimeError:
+     result = asyncio.run(self.search_orchestrator.search(query))
+ else:
+     # ya hay loop, usar await
```

### 12. `core/code_assistant.py:166`
**Colisión de IDs**: `datetime.now().timestamp()` puede duplicarse en misma microsegundo
```diff
- improvement_id = f"improvement_{datetime.now().timestamp()}"
+ improvement_id = f"improvement_{datetime.now().timestamp()}_{len(self.proposed_improvements)}"
```

### 13. `core/code_agents/mobile/agente_registrador.py:60`
**NameError**: typo `detalios` en vez de `detalles`
```diff
- json.dumps(detalios) if detalles else None,
+ json.dumps(detalles) if detalles else None,
```

### 14. `core/lector_documentacion.py:197`
**Race condition**: `tempfile.mktemp()` deprecated (CWE-377)
```diff
- temp_path = tempfile.mktemp(suffix=".png")
+ with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
+     temp_path = f.name
```

### 15. `core/system_prompt.py:178-183`
**Hang**: `sudo powermetrics` espera contraseña en background
```diff
- ["sudo", "powermetrics", ...]
+ ["powermetrics", ...]  # sin sudo
```

---

## LÓGICA / Silent Bug (25)

### 16. `core/sandbox.py:96-97`
Bare `except: pass` traga KeyboardInterrupt y SystemExit
```diff
- except:
-     pass
+ except OSError:
+     pass
```

### 17. `core/lector_documentacion.py:343-344`
Mismo bare `except: pass`
```diff
- except:
-     pass
+ except Exception:
+     pass
```

### 18. `core/sandbox.py:217`
Singleton que crea nueva instancia cada vez
```diff
- def get_sandbox() -> Sandbox:
-     return Sandbox()
+ _sandbox: Sandbox | None = None
+ def get_sandbox() -> Sandbox:
+     global _sandbox
+     if _sandbox is None:
+         _sandbox = Sandbox()
+     return _sandbox
```

### 19. `core/sandbox_orchestrator.py:205`
Recursión infinita: `_tarea_generica` se llama a sí misma sin condición de parada
```diff
- def _tarea_generica(self, item):
-     return self._tarea_generica(item)
+ def _tarea_generica(self, item):
+     return True  # delegar a implementación concreta
```

### 20. `core/autonomous_agent.py:196`
`rm -rf` con `shell=False` no expande el glob `/*` — nunca borra nada
```diff
- subprocess.run(["rm", "-rf", str(Path.home() / ".Trash") + "/*"], shell=False)
+ for item in (Path.home() / ".Trash").iterdir():
+     if item.is_dir():
+         shutil.rmtree(item, ignore_errors=True)
+     else:
+         item.unlink(missing_ok=True)
```

### 21. `core/autonomous_agent.py:136`
`shell=True` con input de usuario → inyección de comandos
```diff
- subprocess.run(action.command, shell=True, ...)
+ subprocess.run(shlex.split(action.command), shell=False, ...)
```

### 22. `core/security/hermetic_states.py:84-100`
`set_hermetic_mode(False)` no desbloquea payments/credentials/internet
```diff
  else:
+     self._block_payments = False
+     self._block_credentials = False
+     self._block_internet = False
      logger.info("MODO HERMÉTICO DESACTIVADO")
```

### 23. `core/security/hermetic_states.py:175,192,209`
Decoradores sin `@functools.wraps` — pierden __name__ y __doc__
```diff
+ import functools
- def wrapper(*args, **kwargs):
+ @functools.wraps(func)
+ def wrapper(*args, **kwargs):
```

### 24. `core/code_agents/orchestrator_mobile.py:77-79`
Agente herramientas nunca se ejecuta (dead code)
```diff
  print("...")
+ self.agentes["herramientas"].ejecutar(codigo_optimizado)
```

### 25. `core/ura_anticipation.py:178`
Patrón `"daily"` se guarda pero se busca `"weekly"` → nunca matchea
```diff
- if pattern.pattern_type == "weekly":
+ if pattern.pattern_type == "daily":
```

### 26. `core/agente_maestro.py:70,80`
`_cargar_gobierno()` y `_cargar_supervisor()` definidos pero nunca llamados
```diff
  self._cargar_agentes()
  self._cargar_estados()
  self._cargar_herramientas()
+ self._cargar_gobierno()
+ self._cargar_supervisor()
```

### 27. `core/agente_maestro.py:346-356`
`ejecutar()` retorna `str` pero type hint dice `dict[str, Any]`
```diff
- return self.preguntar(consulta)
+ return {"respuesta": self.preguntar(consulta)}
```

### 28. `agents/agente_sandbox_codigo.py:57-63`
Nuevos archivos nunca se añaden al inventario; escribe disco aunque no cambie nada
```diff
  if rel in inv["archivos"]:
      inv["archivos"][rel]["hash_md5"] = h
      inv["archivos"][rel]["version"] = ver
- INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
+     INVENTARIO.write_text(json.dumps(inv, indent=2, ensure_ascii=False))
```

### 29. `agents/agente_sandbox_codigo.py:89`
`archivo.name` descarta estructura de directorios → archivo colocado en lugar incorrecto
```diff
- prod_path = PRODUCCION / rel
+ prod_path = PRODUCCION / archivo.name.replace("__", "/")
```

### 30. `agents/agente_sandbox_codigo.py:130`
Versión anterior hardcodeada en vez de leída del inventario
```diff
- crear_ramal(rel, "version_anterior", ...)
+ inv = cargar_inventario()
+ v_old = inv["archivos"].get(rel, {}).get("version", "desconocida")
+ crear_ramal(rel, v_old, ...)
```

### 31. `core/healthcheck.py:95`
`check_output_files()` excluido de `overall_status` → falsos positivos
```diff
- all([results["ollama"], results["redis"], results["pm2"]])
+ all([results["ollama"], results["redis"], results["pm2"], results["output_files"]])
```

### 32. `agents/agente_critico.py:112`
Glob `agente_*.py` ignora agentes como `leyes_agent.py`, `cocina_agent.py`
```diff
- for f in sorted(self.agents_dir.glob("agente_*.py")):
+ for f in sorted(self.agents_dir.glob("*agente*.py")):
+ for f in sorted(self.agents_dir.glob("*_agent*.py")):
```

### 33. `core/disk_cleaner.py:73,85,97,110`
Espacio liberado con estimaciones hardcodeadas, no medido realmente
```diff
- espacio_liberado_mb += 50.0  # Estimación
+ free_before = psutil.disk_usage("/").free
+ # ... operación ...
+ espacio_liberado_mb += (psutil.disk_usage("/").free - free_before) / (1024*1024)
```

### 34. `core/autonomous_maintenance.py:64`
Ventana de 1 minuto para diario — si el loop cae en 23:53 o 23:57, se pierde el día
```diff
- if hora_actual.hour == 23 and hora_actual.minute == 55:
+ if hora_actual.hour == 23 and hora_actual.minute >= 55 and self._last_diary_date != today:
+     self._last_diary_date = today
```

### 35. `core/lector_documentacion.py:201-206`
Si `analizar_imagen()` lanza excepción, el archivo temporal nunca se borra
```diff
- respuesta = analizar_imagen(temp_path, prompt)
- os.unlink(temp_path)
+ try:
+     respuesta = analizar_imagen(temp_path, prompt)
+ finally:
+     os.unlink(temp_path)
```

### 36. `core/conversation_truncator.py:78`
`hash()` no determinista entre procesos → cache no portable
```diff
- text_hash = str(hash(text))
+ text_hash = hashlib.sha256(text.encode()).hexdigest()
```

### 37. `agents/agente_verificador_tareas.py:303`
Markdown de Telegram rompe con underscores en nombres de agentes
```diff
- "parse_mode": "Markdown",
+ "parse_mode": "HTML",
+ # o escapar: text.replace("_", "\\_")
```

### 38. `core/agente_documentador.py:99`
`module.split(".")[0]` devuelve "" para imports relativos
```diff
- top = node.module.split(".")[0]
+ top = node.module.lstrip(".").split(".")[0]
+ if top:
+     deps.add(top)
```

### 39. `core/agente_documentador.py:INTENT_KEYWORDS`
Keyword `"automatiz"` no matchea agentes con `"automatizacion"`
```diff
- "automatiz": "automatizacion",
+ "automatiz": "automatizacion",
+ "automatizac": "automatizacion",
```

### 40. `agents/agente_auditor.py:120-121`
`_parse_ts()` llamado 2 veces por evento (ineficiencia)
```diff
- e for e in eventos
- if self._parse_ts(e.get("timestamp", "")) and self._parse_ts(e.get("timestamp", "")) > ventana
+ for e in eventos:
+     ts = self._parse_ts(e.get("timestamp", ""))
+     if ts and ts > ventana:
+         eventos.append(e)
```

---

## ESTILO / Mantenibilidad (10)

### 41. `core/conversation_truncator.py:9` — `deque` importado pero no usado
### 42. `core/conversation_truncator.py:10` — `Optional` importado pero no usado
### 43. `core/disk_monitor.py:7` — `sys` importado pero no usado
### 44. `core/autonomous_maintenance.py:14` — `hacer_backup` importado pero no usado
### 45. `core/agente_maestro.py:360` — Type hint `AgenteMaestro` debe ser `AgenteMaestro | None`
### 46. `core/code_agents/mobile/agente_registrador.py:29-99` — `sqlite3.connect()` sin context manager, leaks en error
### 47. `core/action_signer.py:152` — `QVBoxLayout` anidado redundante (debería ser `QHBoxLayout`)
### 48. `core/code_agents/tools/install_tools.py:35` — bare `except:` traga KeyboardInterrupt
### 49. `core/buscadores/buscador_documentacion.py:7` — `timezone` importado pero no usado
### 50. `agents/verificador_procesos_gx10.py` — archivo referenciado pero no existe

---

## RESUMEN

| Tipo | Cantidad |
|------|---------|
| Crash / Runtime Error | 15 |
| Lógica / Silent Bug | 25 |
| Estilo / Mantenibilidad | 10 |
| **TOTAL** | **50** |

### Top 5 a corregir YA:
1. `health_monitor.py:85,91` — NameError que rompe en producción
2. `agente_registrador.py:60` — NameError `detalios` cada vez que se registra
3. `ura_anticipation.py:191` — ValueError cada ciclo de anticipación
4. `hermetic_states.py:84-100` — Modo hermético no se puede desactivar
5. `agente_maestro.py:70,80` — Supervisor y gobierno nunca arrancan
