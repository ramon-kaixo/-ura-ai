#!/usr/bin/env python3
"""
Genera o actualiza los docstrings obligatorios en los 28 archivos CRITICAL.
Formato según REGLA_DOCSTRING.md:
  Módulo: ruta
  Propósito: ...
  Dependencias principales: ...
  Reglas especiales: ...
"""

import sys
from pathlib import Path

PROJECT = Path.home() / "URA/ura_ia_1972"

FILES_INFO = {
    "core/agente_documentador.py": {
        "modulo": "core/agente_documentador.py",
        "proposito": "Cataloga y documenta automáticamente todos los agentes del ecosistema URA usando análisis AST.",
        "dependencias": "ast, json, pathlib, importlib",
        "reglas": "No ejecuta código externo; solo lee y analiza estructura de archivos.",
    },
    "core/auto_healing.py": {
        "modulo": "core/auto_healing.py",
        "proposito": "Sistema de auto-reparación: detecta servicios caídos, abre circuit breakers, reinicia procesos fallidos.",
        "dependencias": "subprocess, time, CircuitBreaker, NetworkAuditSystem",
        "reglas": "No reinicia agentes críticos sin confirmación. Usa backoff exponencial.",
    },
    "core/autonomous_agent.py": {
        "modulo": "core/autonomous_agent.py",
        "proposito": "Agente autónomo que ejecuta acciones del sistema (vaciar trash, matar zombies, rotar logs).",
        "dependencias": "subprocess, shlex, shutil, psutil, pathlib",
        "reglas": "NUNCA usar shell=True. Verificar comando antes de ejecutar. Backups antes de borrar.",
    },
    "core/autonomous_maintenance.py": {
        "modulo": "core/autonomous_maintenance.py",
        "proposito": "Mantenimiento autónomo diario: escribe diario URA, rota logs, verifica espacio en disco.",
        "dependencias": "datetime, psutil, URAdiary, ThreadCleaner, monitorear",
        "reglas": "Ventana de escritura diario entre 23:55-23:59. Nunca bloquear el bucle principal.",
    },
    "core/backup_system.py": {
        "modulo": "core/backup_system.py",
        "proposito": "Backup automático a disco externo Toshiba con rotación de versiones.",
        "dependencias": "pathlib, shutil, psutil, schedule",
        "reglas": "Verificar que disco Toshiba esté montado antes de cualquier operación.",
    },
    "core/buscadores/buscador_documentacion.py": {
        "modulo": "core/buscadores/buscador_documentacion.py",
        "proposito": "Busqueda semántica en documentación del proyecto usando embeddings y ChromaDB.",
        "dependencias": "chromadb, sentence_transformers, pathlib, datetime",
        "reglas": "NO conectarse a internet. Solo buscar en docs locales.",
    },
    "core/code_agents/generators/generator_parser.py": {
        "modulo": "core/code_agents/generators/generator_parser.py",
        "proposito": "Parser de código generado por agentes. Valida sintaxis Python y extrae funciones/clases.",
        "dependencias": "ast, json, re, pathlib",
        "reglas": "Rechazar código con eval() o exec(). Validar toda salida antes de aceptar.",
    },
    "core/code_agents/mobile/agente_registrador.py": {
        "modulo": "core/code_agents/mobile/agente_registrador.py",
        "proposito": "Registro SQLite de agentes móviles: historial de ejecuciones, versiones y metadatos.",
        "dependencias": "sqlite3, json, datetime, pathlib",
        "reglas": "Usar context managers para todas las conexiones SQLite. Nunca dejar conexiones abiertas.",
    },
    "core/code_agents/orchestrator_mobile.py": {
        "modulo": "core/code_agents/orchestrator_mobile.py",
        "proposito": "Orquestador de agentes móviles: coordina generación, herramientas, testing y despliegue.",
        "dependencias": "json, pathlib, subprocess, AgenteHerramientas",
        "reglas": "Ejecutar herramientas solo en sandbox. Nunca ejecutar código sin validación previa.",
    },
    "core/code_agents/tools/install_tools.py": {
        "modulo": "core/code_agents/tools/install_tools.py",
        "proposito": "Verifica e instala dependencias del sistema (pip, brew, apt).",
        "dependencias": "subprocess, logging, json",
        "reglas": "SOLO leer comandos. No ejecutar con privilegios elevados. Capturar todos los errores.",
    },
    "core/code_assistant.py": {
        "modulo": "core/code_assistant.py",
        "proposito": "Analiza archivos Python y propone mejoras con ID único para seguimiento.",
        "dependencias": "pathlib, datetime, uuid, json",
        "reglas": "Propuestas deben ser idempotentes. No modificar archivos directamente.",
    },
    "core/consciousness_orchestrator.py": {
        "modulo": "core/consciousness_orchestrator.py",
        "proposito": "Orquestador de niveles de conciencia URA: coordina comunicación y resuelve conflictos entre niveles.",
        "dependencias": "json, datetime, pathlib, threading",
        "reglas": "Priorizar el nivel más alto en conflictos. Registrar todas las decisiones.",
    },
    "core/conversation_truncator.py": {
        "modulo": "core/conversation_truncator.py",
        "proposito": "Trunca conversaciones largas para no exceder límites de tokens usando caché de resúmenes.",
        "dependencias": "hashlib, collections.deque, pathlib, json",
        "reglas": "Usar SHA256 para hashing. No truncar mensajes a mitad. Mantener contexto de 10 mensajes.",
    },
    "core/disk_cleaner.py": {
        "modulo": "core/disk_cleaner.py",
        "proposito": "Limpia automáticamente caches (pip, npm, brew) y archivos temporales del sistema.",
        "dependencias": "subprocess, psutil, pathlib, json",
        "reglas": "Medir espacio real liberado. No usar valores hardcodeados en reportes.",
    },
    "core/disk_monitor.py": {
        "modulo": "core/disk_monitor.py",
        "proposito": "Monitorea espacio en disco y envía alertas cuando baja del umbral configurado.",
        "dependencias": "psutil, logging, datetime",
        "reglas": "Alertar solo una vez por umbral. No spam de notificaciones.",
    },
    "core/health_monitor.py": {
        "modulo": "core/health_monitor.py",
        "proposito": "Monitor de salud del sistema URA: verifica estado de Ollama y recursos cada 5 minutos.",
        "dependencias": "subprocess, threading, datetime, logging, requests",
        "reglas": "Intervalo mínimo de 300 segundos entre alertas. Detectar caídas de Ollama.",
    },
    "core/healthcheck.py": {
        "modulo": "core/healthcheck.py",
        "proposito": "Healthcheck completo: verifica Ollama, Redis, PM2 y archivos de salida. Determina estado general.",
        "dependencias": "subprocess, pathlib, json, datetime",
        "reglas": "Incluir check_output_files en overall_status. No falsos positivos.",
    },
    "core/lector_documentacion.py": {
        "modulo": "core/lector_documentacion.py",
        "proposito": "Lee y analiza documentación en PDFs, Markdown e imágenes con OCR y embeddings.",
        "dependencias": "pathlib, re, json, datetime, tempfile, asyncio",
        "reglas": "Usar NamedTemporaryFile en vez de mktemp. Limpiar archivos temporales SIEMPRE con try/finally.",
    },
    "core/maintenance_cycle.py": {
        "modulo": "core/maintenance_cycle.py",
        "proposito": "Ejecuta tareas de mantenimiento periódico: backup, limpieza, verificación de integridad.",
        "dependencias": "datetime, time, json, pathlib, subprocess",
        "reglas": "Tolerancia a fallos: un error no para otros. Loggear cada tarea completada.",
    },
    "core/query_decomposer.py": {
        "modulo": "core/query_decomposer.py",
        "proposito": "Descompone consultas complejas en subconsultas para distribuir a agentes especializados.",
        "dependencias": "re, json, logging",
        "reglas": "Max 5 subconsultas por consulta. No crear dependencias circulares.",
    },
    "core/sandbox.py": {
        "modulo": "core/sandbox.py",
        "proposito": "Entorno aislado para ejecutar código Python de forma segura con import dinámico controlado.",
        "dependencias": "importlib, subprocess, pathlib, logging",
        "reglas": "Nunca ejecutar código sin sandbox. Capturar OSError. No propagar excepciones del sandbox.",
    },
    "core/sandbox_orchestrator.py": {
        "modulo": "core/sandbox_orchestrator.py",
        "proposito": "Orquesta ejecuciones en sandbox: gestiona cola de tareas, log de ejecuciones y rotación de entornos.",
        "dependencias": "json, datetime, pathlib, Sandbox",
        "reglas": "Máximo de ejecuciones concurrentes. Rotar logs cada 1000 entradas.",
    },
    "core/search_cache.py": {
        "modulo": "core/search_cache.py",
        "proposito": "Cache de resultados de búsqueda en disco para evitar consultas repetidas costosas.",
        "dependencias": "pathlib, json, hashlib",
        "reglas": "Fallback a cache local si disco externo no disponible. TTL máximo 24h.",
    },
    "core/secure_trash.py": {
        "modulo": "core/secure_trash.py",
        "proposito": "Papelera segura que versiona archivos antes de borrarlos para permitir restauración.",
        "dependencias": "shutil, pathlib, json, datetime",
        "reglas": "Nunca borrar sin versionar. Mantener mínimo 3 versiones.",
    },
    "core/security/hermetic_states.py": {
        "modulo": "core/security/hermetic_states.py",
        "proposito": "Estados herméticos de seguridad: bloquea pagos, credenciales e internet según modo activo.",
        "dependencias": "enum, functools, threading, json",
        "reglas": "Decoradores SIEMPRE verificados antes de ejecutar funciones sensibles. Reset total al desactivar.",
    },
    "core/system_prompt.py": {
        "modulo": "core/system_prompt.py",
        "proposito": "Gestiona el system prompt dinámico del asistente URA con detección de temperatura del sistema.",
        "dependencias": "subprocess, pathlib, json",
        "reglas": "powermetrics sin sudo. Timeout de 10s. Fallback a temperatura desconocida.",
    },
    "core/toshiba_backup.py": {
        "modulo": "core/toshiba_backup.py",
        "proposito": "Backup específico a disco Toshiba externo con verificación de montaje previo.",
        "dependencias": "pathlib, shutil, logging",
        "reglas": "Verificar montaje ANTES de cualquier operación. No crear directorios en ruta no montada.",
    },
    "core/ura_anticipation.py": {
        "modulo": "core/ura_anticipation.py",
        "proposito": "Sistema de anticipación: detecta patrones de uso diarios y horarios para generar predicciones.",
        "dependencias": "datetime, json, pathlib, threading",
        "reglas": "Comparar patrones con formato HH:MM usando split. Validar antes de convertir a int.",
    },
}


def update_docstring(filepath: Path, info: dict) -> bool:
    """Actualiza el docstring de un archivo .py con el formato obligatorio."""
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return False

    # Build new docstring
    lines = [
        '"""',
        f"Módulo: {info['modulo']}",
        f"Propósito: {info['proposito']}",
        f"Dependencias principales: {info['dependencias']}",
        f"Reglas especiales: {info['reglas']}",
        '"""',
    ]
    new_docstring = "\n".join(lines)

    # Find and replace existing docstring
    # Pattern: starts with """ or ''' after shebang
    import re

    # Strip shebang and whitespace, find the first docstring
    stripped = content.lstrip()
    if stripped.startswith("#!"):
        # Find end of shebang line
        shebang_end = content.find("\n") + 1
        before = content[:shebang_end]
        rest = content[shebang_end:].lstrip()
    else:
        before = ""
        rest = content

    # Find existing docstring (triple quotes)
    match = re.match(r'([ \t]*)(?:"""|\'\'\')(.*?)(?:"""|\'\'\')', rest, re.DOTALL)
    if match:
        indent = match.group(1)
        rest_after = rest[match.end() :]
        new_content = before + indent + new_docstring + "\n" + rest_after
    else:
        # No existing docstring, insert at top
        new_content = before + new_docstring + "\n" + rest

    filepath.write_text(new_content, encoding="utf-8")
    return True


def main():
    updated = 0
    failed = 0
    for rel_path, info in FILES_INFO.items():
        filepath = PROJECT / rel_path
        if not filepath.exists():
            print(f"  SKIP (no existe): {rel_path}")
            failed += 1
            continue
        if update_docstring(filepath, info):
            print(f"  ✅ {rel_path}")
            updated += 1
        else:
            print(f"  ❌ {rel_path}")
            failed += 1

    print(f"\nResultado: {updated} actualizados, {failed} fallidos")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
