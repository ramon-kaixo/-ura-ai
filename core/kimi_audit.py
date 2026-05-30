#!/usr/bin/env python3
"""
kimi_audit.py — Auditoría Kimi-Dev 72B con prompt mejorado, watchdog y auto-skip.
"""

import json
import signal
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

KIMI_PORT = 8292
LLAMA_SERVER = str(Path.home() / "llama.cpp/build_cuda/bin/llama-server")
MODEL = str(Path.home() / "models/kimi-dev/Kimi-Dev-72B-abliterated-Q8_0.gguf")
API_URL = f"http://127.0.0.1:{KIMI_PORT}/v1/chat/completions"

SYSTEM_PROMPT = """Eres un revisor de codigo Python en el proyecto URA (asistente IA multi-agente con 80+ agentes).

Tu tarea: encontrar SOLO bugs que romperian en produccion.

Tipos de bugs que buscar:
- NameError: variables/funciones mal escritas, imports rotos
- TypeError: tipos incorrectos, str vs dict, int vs str
- ValueError: conversiones que fallan ("14:00" -> int)
- Recursion infinita, deadlocks, procesos zombie
- Seguridad: shell=True, eval(), exec(), path traversal
- Recursos: archivos sin cerrar, temp files sin borrar
- Logica: condiciones imposibles, funciones que nunca se llaman

REGLAS ESTRICTAS:
1. SOLO reporta bugs reales. NADA de estilo ni sugerencias.
2. Formato exacto para cada bug: LINEA | QUE FALLA | COMO ARREGLARLO
3. Maximo 2 lineas por bug. Se conciso.
4. Si no hay bugs: responde solo "OK"

Ejemplo de respuesta valida:
85 | NameError: variable downtenance no existe, debe ser downtime | Cambiar downtenance a downtime"""

FILES = [
    (
        "core/agente_documentador.py",
        "Cataloga y documenta agentes Python del ecosistema URA usando AST.",
    ),
    (
        "core/auto_healing.py",
        "Auto-reparacion: detecta servicios caidos, abre circuit breakers, reinicia procesos.",
    ),
    (
        "core/autonomous_agent.py",
        "Agente autonomo: ejecuta acciones del sistema (limpiar trash, matar zombies). Usa subprocess.",
    ),
    (
        "core/autonomous_maintenance.py",
        "Mantenimiento autonomo diario: escribe diario, rota logs, verifica disco. Bucle 5 min.",
    ),
    ("core/backup_system.py", "Backup automatico a Toshiba externa con rotacion de versiones."),
    (
        "core/buscadores/buscador_documentacion.py",
        "Busqueda semantica en Markdown usando ChromaDB + embeddings.",
    ),
    (
        "core/code_agents/generators/generator_parser.py",
        "Parser de codigo generado por agentes. Valida sintaxis Python.",
    ),
    (
        "core/code_agents/mobile/agente_registrador.py",
        "Registro SQLite de agentes moviles: historial, versiones, metadatos.",
    ),
    (
        "core/code_agents/orchestrator_mobile.py",
        "Orquestador movil: coordina generacion, herramientas, testing y despliegue en 6 pasos.",
    ),
    (
        "core/code_agents/tools/install_tools.py",
        "Herramientas de instalacion: verifica pip, brew, apt.",
    ),
    ("core/code_assistant.py", "Asistente de codigo que propone mejoras con ID unico."),
    (
        "core/consciousness_orchestrator.py",
        "Orquestador de niveles de conciencia URA. Coordina comunicacion y conflictos.",
    ),
    (
        "core/conversation_truncator.py",
        "Trunca conversaciones largas usando cache de resumenes con hash.",
    ),
    ("core/disk_cleaner.py", "Limpia disco: elimina caches, logs antiguos, temporales."),
    ("core/disk_monitor.py", "Monitorea espacio en disco con alertas por umbral."),
    (
        "core/health_monitor.py",
        "Monitor de salud: uptime, CPU, RAM. Detecta downtime y envia alertas.",
    ),
    ("core/healthcheck.py", "Healthcheck completo: Ollama, Redis, PM2, archivos de salida."),
    (
        "core/lector_documentacion.py",
        "Lector de documentacion: PDFs, Markdown, imagenes con OCR y embeddings.",
    ),
    (
        "core/maintenance_cycle.py",
        "Ciclo de mantenimiento programado: backup, limpieza, verificacion.",
    ),
    (
        "core/query_decomposer.py",
        "Descompone consultas complejas en subconsultas para agentes especializados.",
    ),
    (
        "core/sandbox.py",
        "Entorno aislado para ejecutar codigo de forma segura con import dinamico.",
    ),
    (
        "core/sandbox_orchestrator.py",
        "Orquestador del sandbox: cola de tareas, log, rotacion de entornos.",
    ),
    ("core/search_cache.py", "Cache de busquedas en disco Toshiba. Evita consultas repetidas."),
    ("core/secure_trash.py", "Papelera segura: versiona archivos antes de borrar."),
    (
        "core/security/hermetic_states.py",
        "Estados hermeticos: bloquea payments, credentials, internet. Decoradores de proteccion.",
    ),
    (
        "core/system_prompt.py",
        "Gestiona system prompt del asistente con deteccion de temperatura Mac.",
    ),
    ("core/toshiba_backup.py", "Backup especifico a Toshiba. Verifica montaje antes de copiar."),
    (
        "core/ura_anticipation.py",
        "Anticipacion: detecta patrones de uso (diarios, horarios) y genera predicciones.",
    ),
]

PROJECT = str(Path.home() / "URA/ura_ia_1972")

kimi_pid = None


def start_kimi():
    global kimi_pid
    # Kill any existing on this port
    subprocess.run(["pkill", "-f", f"llama-server.*{KIMI_PORT}"], capture_output=True)
    time.sleep(2)
    cmd = [
        LLAMA_SERVER,
        "-m",
        MODEL,
        "--port",
        str(KIMI_PORT),
        "--host",
        "127.0.0.1",
        "-ngl",
        "80",
        "-c",
        "16384",
        "--mlock",
    ]
    kimi_pid = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print(f"  Kimi PID: {kimi_pid.pid}")
    for i in range(120):
        try:
            urllib.request.urlopen(f"http://127.0.0.1:{KIMI_PORT}/health", timeout=3)  # nosec B310
            print(f"  Kimi listo ({i * 2}s)")
            return True
        except:
            time.sleep(2)
    print("  ERROR: Kimi no arranco")
    return False


def restart_kimi():
    global kimi_pid
    if kimi_pid:
        kimi_pid.terminate()
        try:
            kimi_pid.wait(timeout=10)
        except:
            kimi_pid.kill()
    return start_kimi()


def check_kimi():
    try:
        urllib.request.urlopen(f"http://127.0.0.1:{KIMI_PORT}/health", timeout=3)  # nosec B310
        return True
    except:
        return False


def send_review(filepath, context, max_retries=3):
    code = Path(PROJECT, filepath).read_text(encoding="utf-8", errors="replace")
    lines = code.count("\n") + 1

    user_msg = f"CONTEXTO DEL ARCHIVO: {context}\n\nArchivo: {filepath} ({lines} lineas)\n```python\n{code}\n```"

    payload = json.dumps(
        {
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            "max_tokens": 1200,
            "temperature": 0.1,
            "stream": False,
        }
    ).encode("utf-8")

    for attempt in range(1, max_retries + 1):
        if attempt > 1:
            print(f"  (reintento {attempt})...", end=" ", flush=True)
            if not check_kimi():
                if not restart_kimi():
                    return {"ok": False, "error": "Kimi no disponible"}
        try:
            req = urllib.request.Request(
                API_URL, data=payload, headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=600) as resp:  # nosec B310
                data = json.loads(resp.read())
                content = data["choices"][0]["message"]["content"]
                return {"ok": True, "content": content}
        except Exception as e:
            if attempt == max_retries:
                return {"ok": False, "error": str(e)}
            time.sleep(5)
    return {"ok": False, "error": "max retries"}


def main():
    global kimi_pid
    out_dir = Path.home() / "logs/auditoria_multimodelo"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"review_final_kimi-dev-72b_{time.strftime('%Y%m%d_%H%M')}.md"

    signal.signal(
        signal.SIGINT, lambda s, f: (kimi_pid.terminate() if kimi_pid else None, sys.exit(0))
    )
    signal.signal(
        signal.SIGTERM, lambda s, f: (kimi_pid.terminate() if kimi_pid else None, sys.exit(0))
    )

    print("=== Auditoria Kimi-Dev 72B ===")
    print(f"Modelo: {MODEL}")
    print(f"Archivos: {len(FILES)}")
    print(f"Output: {out_path}")

    if not start_kimi():
        print("FATAL: No se pudo iniciar Kimi-Dev")
        return 1

    with open(out_path, "w", encoding="utf-8") as out:
        out.write(f"# Auditoria Kimi-Dev 72B — {time.ctime()}\n")
        out.write("**Prompt:** mejorado (SOLO bugs, formato rigido)\n")
        out.write("**GPU:** -ngl 80 | **Contexto:** 16K | **Watchdog:** activo\n")
        out.write("---\n")

        total = len(FILES)
        bugs_total = 0

        for i, (filepath, context) in enumerate(FILES, 1):
            fp = Path(PROJECT, filepath)
            if not fp.exists():
                out.write(f"\n## {filepath}  [NO ENCONTRADO]\n\n")
                print(f"[{i}/{total}] SKIP: {filepath}")
                continue

            print(f"[{i}/{total}] {filepath}...", end=" ", flush=True)
            result = send_review(filepath, context)

            if result["ok"]:
                review = result["content"]
                out.write(f"\n## {filepath}\n\n*Contexto:* {context}\n\n{review}\n\n")
                import re

                bug_lines = len(re.findall(r"\d+\s*\|", review))
                if bug_lines > 0:
                    print(f"→ {bug_lines} bugs")
                    bugs_total += bug_lines
                else:
                    print("OK")
            else:
                out.write(f"\n## {filepath}\n\nERROR: {result['error']}\n\n")
                print(f"ERROR: {result['error']}")

        out.write(f"\n---\n**TOTAL BUGS: {bugs_total}** | Archivos: {total}\n")

    if kimi_pid:
        kimi_pid.terminate()

    print(f"\nCOMPLETADO: {bugs_total} bugs en {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
