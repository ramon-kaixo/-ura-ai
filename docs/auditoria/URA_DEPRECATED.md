# URA — Elementos retirados y deprecated

Este archivo registra todos los elementos que han sido retirados del sistema URA. El propósito es mantener la memoria del sistema completa aunque el código esté limpio.

---

## llama3.2:latest
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**: 
  - connectors/ollama_connector.py:111 (default_model)
  - core/ura_memory.py:30 (MODEL_MEMORY_PROFILE)
  - core/web_search.py:21 (DEFAULT_MODEL)
  - config/department_profiles.json:109 (mapeo de departamento)
- **Motivo**: Modelo demasiado pequeño (1B, 2 GB) para mantener coherentemente la identidad persistente de URA, las 10 capacidades registradas y las reglas de comportamiento estrictas. Síntoma habitual: URA respondía "no puedo ver tu pantalla", "como IA no tengo acceso a…", dudando de capacidades que sí tiene instaladas.
- **Sustituido por**: qwen2.5:7b-instruct
- **Cómo recuperarlo**: 
  - Revertir los cambios en los archivos mencionados
  - Cambiar default_model='llama3.2:latest' en connectors/ollama_connector.py
  - Restaurar "llama3.2:latest": (4, 400) en core/ura_memory.py
  - Cambiar DEFAULT_MODEL = "llama3.2:latest" en core/web_search.py
  - Restaurar "llama3.2:latest": "gestion" en config/department_profiles.json

## llama3.2:3b
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**:
  - core/workflow_engine.py:104 (model='llama3.2:3b')
  - core/technical_director.py:22 (model='llama3.2:3b')
  - core/technical_director.py:319 (model='llama3.2:3b')
  - config/settings.json:7 ("preferred_model": "llama3.2:3b")
- **Motivo**: Modelo obsoleto que causaba que URA se conectara al modelo equivocado repetidamente. El modelo estaba hardcodeado en múltiples lugares, lo que dificultaba su mantenimiento y causaba inconsistencias.
- **Sustituido por**: qwen2.5:7b-instruct
- **Cómo recuperarlo**:
  - Revertir los cambios en los archivos mencionados
  - Cambiar model='llama3.2:3b' en core/workflow_engine.py
  - Cambiar model='llama3.2:3b' en core/technical_director.py (líneas 22 y 319)
  - Cambiar "preferred_model": "llama3.2:3b" en config/settings.json

## llama3:latest
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**:
  - core/ura_memory.py:29 ("llama3:latest": (8, 600))
  - config/department_profiles.json:110 ("llama3:latest": "gestion")
  - bench_models.py (for model in ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct", "llama3:latest"])
- **Motivo**: Modelo obsoleto que ya no se usa en el sistema. Se mantiene solo en mapeos de departamentos y scripts de benchmark.
- **Sustituido por**: qwen2.5:7b-instruct
- **Cómo recuperarlo**:
  - Restaurar "llama3:latest": (8, 600) en core/ura_memory.py
  - Restaurar "llama3:latest": "gestion" en config/department_profiles.json
  - Añadir "llama3:latest" al bucle en bench_models.py

## llama3:70b
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**:
  - core/consensus_system.py (LLAMA3_70B = "llama3:70b")
  - config/department_profiles.json:103 ("llama3:70b": "sistema")
  - core/knowledge_base.json (referencias en datos de conocimiento)
- **Motivo**: Modelo obsoleto que ya no se usa en el sistema. Era una constante en consensus_system.py y un mapeo de departamento.
- **Sustituido por**: No hay sustituto directo, ya no se usa en el sistema.
- **Cómo recuperarlo**:
  - Restaurar LLAMA3_70B = "llama3:70b" en core/consensus_system.py
  - Restaurar "llama3:70b": "sistema" en config/department_profiles.json
  - Restaurar referencias en core/knowledge_base.json

## llama3.2:1b
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**:
  - config/department_profiles.json:108 ("llama3.2:1b": "lenguaje")
- **Motivo**: Modelo obsoleto que ya no se usa en el sistema. Era solo un mapeo de departamento.
- **Sustituido por**: No hay sustituto directo, ya no se usa en el sistema.
- **Cómo recuperarlo**:
  - Restaurar "llama3.2:1b": "lenguaje" en config/department_profiles.json

## get_telegram_bridge() en módulos secundarios
- **Retirado**: 24 Abril 2026, 03:55 AM
- **Ubicación original**:
  - core/terminal_gateway.py:68 (self.telegram_bridge = get_telegram_bridge())
  - core/security_policy.py:138 (bridge = get_telegram_bridge())
  - core/self_healing_system.py:333 (telegram_bridge = get_telegram_bridge())
- **Motivo**: El singleton de Telegram bridge no funcionaba correctamente porque cada módulo tenía su propia copia de la variable global _telegram_bridge. Esto causaba que "Polling de callbacks iniciado" apareciera dos veces en los logs, indicando múltiples instancias.
- **Sustituido por**: Inyección de dependencias desde main_final.py (pendiente de implementación)
- **Cómo recuperarlo**:
  - Restaurar self.telegram_bridge = get_telegram_bridge() en core/terminal_gateway.py
  - Restaurar bridge = get_telegram_bridge() en core/security_policy.py
  - Restaurar telegram_bridge = get_telegram_bridge() en core/self_healing_system.py

## Referencias hardcodeadas de modelo en módulos (Alternativa 1)
- **Retirado**: 24 Abril 2026, 04:10 AM
- **Ubicación original**:
  - core/workflow_engine.py:104 (model='qwen2.5:7b-instruct')
  - core/technical_director.py:22 (model='qwen2.5:7b-instruct')
  - core/technical_director.py:319 (model='qwen2.5:7b-instruct')
  - connectors/ollama_connector.py:114 (default_model='qwen2.5:7b-instruct')
  - config/settings.json:7 ("preferred_model": "qwen2.5:7b-instruct")
- **Motivo**: El modelo estaba hardcodeado en múltiples lugares del código, lo que dificultaba su mantenimiento y causaba inconsistencias. Cada vez que se cambiaba el modelo, solo se cambiaba algunos lugares pero no todos, causando que URA se conectara al modelo equivocado repetidamente.
- **Sustituido por**: Configuración centralizada en config/model_config.json con función get_active_model() en core/model_config.py
- **Cómo recuperarlo**:
  - Restaurar model='qwen2.5:7b-instruct' en core/workflow_engine.py:104
  - Restaurar model='qwen2.5:7b-instruct' en core/technical_director.py:22 y 319
  - Restaurar default_model='qwen2.5:7b-instruct' en connectors/ollama_connector.py:114
  - Restaurar "preferred_model": "qwen2.5:7b-instruct" en config/settings.json:7
  - Eliminar core/model_config.py y config/model_config.json

## Archivos con nombres de hash (URA_IA_1972_COMPLETO)
- **Retirado**: 24 Abril 2026, 09:19 AM
- **Ubicación original**: `/Users/ramonesnaola/URA_IA_1972_COMPLETO/`
- **Archivos afectados**: 72 archivos con prefijo de hash de 32 caracteres hexadecimales
- **Ejemplos**:
  - `ddf210b81357fe97057460f5fb132af7_model_config.py` → `model_config.py`
  - `c9d787eeeb96f439ec62e88a2a6c7e8d_ura_identity.py` → `ura_identity.py`
  - `dd313e71461401b9c8f04edc844a9ef3_telegram_security_bridge.py` → `telegram_security_bridge.py`
  - `e52e9139ac0425043d76a6c25455ca2a_evolutionary_system.py` → `evolutionary_system.py`
  - `d29b9de845b6e602c6c5bdde27abf1d5_ura_identity.json` → `ura_identity.json`
  - `aa3e1b474a11c796bb17c8f735f8ec4c_model_config.json` → `model_config.json`
- **Motivo**: Los archivos tenían nombres ilegibles con hashes que dificultaban el mantenimiento. Los hashes fueron generados por Windsurf/Codeium como parte de su sistema de tracking.
- **Acción tomada**:
  - Renombrados 72 archivos quitando el prefijo de hash
  - Movidos 5 archivos faltantes a URA_App (URA_launcher.py, agente_cocina.py, agente_creativo.py, agente_policia_v2.py, ollama_connector.py)
- **Cómo recuperarlo**: Los archivos originales con hash ya no existen. Si se necesita restaurar, deben buscarse en backups o en el historial de Windsurf.
