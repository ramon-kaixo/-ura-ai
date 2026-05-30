#!/usr/bin/env python3
"""
Módulo: ura_panel.py
Propósito: Panel web Flask para monitoreo y control del sistema URA.
Dependencias principales: flask, json, pathlib, core.ura_metaconsciousness
Reglas especiales: Solo lectura y visualización. No ejecuta acciones del sistema.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template_string, request
import requests

from core.ura_metaconsciousness import URAMetaconsciousness
from core.ura_value_system import get_ura_value_system
from core.smart_cache import get_smart_cache
from core.autonomous_agent import get_autonomous_agent
from services.apple_integration import get_apple_integration
from core.code_assistant import get_code_assistant
from core.dual_verification import get_dual_verification
from core.forensic_scribe import get_forensic_scribe
from core.error_cross_reference import get_error_cross_reference
from core.conflict_detector import get_conflict_detector
from core.research_pipeline import get_research_pipeline
from core.vocabulary_department import get_vocabulary_manager, get_crystal_limiter
from core.sandbox_orchestrator import get_sandbox_orchestrator
from core.central_router import get_central_router

APP_PATH = Path(__file__).parent
OUTPUT_PATH = APP_PATH / "core" / "data" / "output"
FEEDBACK_PATH = APP_PATH / "core" / "data" / "feedback"
FEEDBACK_PATH.mkdir(parents=True, exist_ok=True)
LOG_PATH = APP_PATH / "core" / "LOG_ACTIVIDAD_URA.md"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = Flask(__name__)

# Inicializar módulos de conciencia
metaconsciousness = URAMetaconsciousness()
value_system = get_ura_value_system()
smart_cache = get_smart_cache(default_ttl=300)
autonomous_agent = get_autonomous_agent()
apple_integration = get_apple_integration()
code_assistant = get_code_assistant()
dual_verification = get_dual_verification()
forensic_scribe = get_forensic_scribe()
error_cross_reference = get_error_cross_reference()
conflict_detector = get_conflict_detector()
research_pipeline = get_research_pipeline()
vocabulary_manager = get_vocabulary_manager()
crystal_limiter = get_crystal_limiter()
sandbox_orchestrator = get_sandbox_orchestrator()
central_router = get_central_router()
_last_research_report: dict = {"topic": None, "full_report": None}


def log_actividad(seccion, accion):
    try:
        ts = datetime.now().strftime("%H:%M")
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(f"{ts} - [PANEL] - {seccion}: {accion}\n")
    except Exception as e:
        logger.error(f"Error log: {e}")


def cargar_json(nombre):
    ruta = OUTPUT_PATH / nombre
    if not ruta.exists():
        return {}
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def cargar_feedback():
    ruta = FEEDBACK_PATH / "feedback.json"
    if not ruta.exists():
        return {"aprobados": [], "rechazados": []}
    try:
        with open(ruta, encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"aprobados": [], "rechazados": []}


def guardar_feedback(feedback):
    with open(FEEDBACK_PATH / "feedback.json", "w", encoding="utf-8") as f:
        json.dump(feedback, f, ensure_ascii=False, indent=2)


TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head><meta charset="UTF-8"><title>URA Panel</title></head>
<body style="background:#111;color:#eee;font-family:sans-serif;padding:20px">
<h1>URA Panel</h1>
<div><h2>Chat</h2>
<input id="msg" style="width:60%;padding:10px"><button onclick="send()">Enviar</button>
<div style="margin-top:10px">
    <button id="btn-ura" onclick="setDest('ura')" style="padding:8px 16px;margin-right:5px;background:#4CAF50;color:white;border:none;border-radius:4px;cursor:pointer">URA</button>
    <button id="btn-windsurf" onclick="setDest('windsurf')" style="padding:8px 16px;margin-right:5px;background:#555;color:white;border:none;border-radius:4px;cursor:pointer">Windsurf</button>
    <button id="btn-openclaw" onclick="setDest('openclaw')" style="padding:8px 16px;background:#555;color:white;border:none;border-radius:4px;cursor:pointer">OpenClaw</button>
</div>
<div id="chat" style="margin-top:20px;background:#222;padding:10px;height:300px;overflow:auto"></div>
</div>
<script>
let currentDest = 'ura';
function setDest(dest) {
    currentDest = dest;
    document.getElementById('btn-ura').style.background = dest === 'ura' ? '#4CAF50' : '#555';
    document.getElementById('btn-windsurf').style.background = dest === 'windsurf' ? '#4CAF50' : '#555';
    document.getElementById('btn-openclaw').style.background = dest === 'openclaw' ? '#4CAF50' : '#555';
}
async function send() {
    let msg = document.getElementById('msg').value;
    if(!msg) return;
    let d = document.getElementById('chat');
    d.innerHTML += `<p><b>Tú:</b> ${msg}</p>`;
    try {
        let r = await fetch('/api/chat', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({message:msg, destination:currentDest})});
        let j = await r.json();
        d.innerHTML += `<p><b>${currentDest.charAt(0).toUpperCase() + currentDest.slice(1)}:</b> ${j.response || j.error}</p>`;
    } catch(e) {
        d.innerHTML += `<p>Error: ${e.message}</p>`;
    }
    document.getElementById('msg').value = '';
}
</script>
</body></html>"""


@app.route("/")
def index():
    return render_template_string(TEMPLATE)


@app.route("/dashboard")
def dashboard():
    """Servir el dashboard de métricas."""
    dashboard_path = APP_PATH / "dashboard" / "metrics_dashboard.html"
    if dashboard_path.exists():
        with open(dashboard_path, encoding="utf-8") as f:
            return f.read()
    return "Dashboard no encontrado", 404


@app.route("/api/metrics")
def api_metrics():
    """API para obtener métricas del sistema."""
    import psutil
    import shutil

    try:
        # CPU
        cpu_percent = psutil.cpu_percent(interval=1)

        # RAM
        ram = psutil.virtual_memory()
        ram_used = round(ram.used / (1024**3), 2)
        ram_percent = ram.percent

        # Disco
        disk = psutil.disk_usage("/")
        disk_percent = disk.percent

        # Temperatura (si está disponible)
        temperature = 0
        try:
            if hasattr(psutil, "sensors_temperatures"):
                temps = psutil.sensors_temperatures()
                if temps:
                    for name, entries in temps.items():
                        if entries:
                            temperature = max(e.current for e in entries)
                            break
        except:
            pass

        # Estado de servicios
        ollama_status = False
        openclaw_status = False

        # Verificar Ollama
        try:
            import requests

            r = requests.get("http://localhost:11434/api/tags", timeout=2)
            ollama_status = r.status_code == 200
        except:
            pass

        # Verificar OpenClaw
        openclaw_status = shutil.which("openclaw") is not None

        return jsonify(
            {
                "cpu": cpu_percent,
                "ram_used": ram_used,
                "ram_percent": ram_percent,
                "disk_percent": disk_percent,
                "temperature": temperature,
                "services": {"ollama": ollama_status, "openclaw": openclaw_status},
                "timestamp": datetime.now().isoformat(),
            }
        )
    except Exception as e:
        logger.error(f"Error obteniendo métricas: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/health")
def health():
    """Endpoint de salud del sistema."""
    import psutil
    import shutil

    # Estado de Ollama
    ollama_status = False
    try:
        import requests

        r = requests.get("http://localhost:11434/api/tags", timeout=2)
        ollama_status = r.status_code == 200
    except:
        pass

    # Estado de OpenClaw
    openclaw_status = shutil.which("openclaw") is not None

    # RAM libre
    ram = psutil.virtual_memory()
    ram_free_gb = round(ram.available / (1024**3), 2)

    # Fecha del último backup
    last_backup = None
    backup_dir = Path.home() / "URA_Backups"
    if backup_dir.exists():
        backups = sorted(backup_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)
        if backups:
            last_backup = datetime.fromtimestamp(backups[0].stat().st_mtime).isoformat()

    return jsonify(
        {
            "ollama": ollama_status,
            "openclaw": openclaw_status,
            "ram_free_gb": ram_free_gb,
            "last_backup": last_backup,
            "timestamp": datetime.now().isoformat(),
        }
    )


@app.route("/api/errors/correlations")
def api_errors_correlations():
    """Cruce de errores: correlaciones, scores y sugerencias."""
    try:
        return jsonify(
            {
                "correlations": error_cross_reference.find_correlations(),
                "module_scores": error_cross_reference.score_modules()[:10],
                "suggestions": error_cross_reference.suggest_refactors(),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/research", methods=["POST"])
def api_research():
    """Ejecutar pipeline de investigación autónoma."""
    try:
        data = request.get_json() or {}
        topic = data.get("topic", "")
        if not topic:
            return jsonify({"error": "topic requerido"}), 400
        result = research_pipeline.execute(topic)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/install", methods=["POST"])
def api_install():
    """Analizar instalación con detector de conflictos."""
    try:
        data = request.get_json() or {}
        package = data.get("package", "")
        version = data.get("version")
        if not package:
            return jsonify({"error": "package requerido"}), 400
        result = conflict_detector.analyze_installation(package, version)
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/sandboxes/status")
def api_sandboxes_status():
    """Estado de los 5 sandboxes."""
    return jsonify(sandbox_orchestrator.get_all_status())


@app.route("/api/sandboxes/accelerate", methods=["POST"])
def api_sandboxes_accelerate():
    """Activa manualmente el ciclo acelerado durante 24h."""
    data = request.get_json() or {}
    reason = data.get("reason", "manual")
    result = sandbox_orchestrator.trigger_accelerated_cycle(reason=reason)
    return jsonify(result)


@app.route("/api/vocabulary/<department>")
def api_vocabulary_get(department):
    """Devuelve el vocabulario técnico de un departamento."""
    vocab = vocabulary_manager.get_vocabulary(department)
    if not vocab:
        return jsonify({"error": f"departamento '{department}' no existe"}), 404
    return jsonify(vocab.to_dict())


@app.route("/api/vocabulary/<department>/add", methods=["POST"])
def api_vocabulary_add(department):
    """Añadir un término al vocabulario de un departamento."""
    vocab = vocabulary_manager.get_vocabulary(department)
    if not vocab:
        return jsonify({"error": f"departamento '{department}' no existe"}), 404
    data = request.get_json() or {}
    term = data.get("term", "").strip()
    definition = data.get("definition", "").strip()
    source = data.get("source", "").strip()
    if not term or not definition:
        return jsonify({"error": "term y definition son requeridos"}), 400
    vocab.add_term(term, definition, source)
    from pathlib import Path as _P

    vocab.save_to_file(_P.home() / ".ura" / "vocabulary" / f"{department}.json")
    return jsonify({"ok": True, "term": term, "total_terms": len(vocab.terms)})


@app.route("/api/forensic/status")
def api_forensic_status():
    """Estado del sistema de análisis forense."""
    try:
        status = forensic_scribe.get_status()
        return jsonify(status)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/reload", methods=["POST"])
def api_reload():
    """Recargar configuración y módulos."""
    try:
        log_actividad("RELOAD", "Recargando módulos")
        # Recargar caché
        global smart_cache
        smart_cache.invalidate("")
        smart_cache = get_smart_cache(default_ttl=300)
        return jsonify({"ok": True, "message": "Módulos recargados"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/feedback", methods=["POST"])
def api_feedback():
    """Recibir feedback del usuario."""
    try:
        data = request.get_json()
        feedback_type = data.get("type", "positive")
        message = data.get("message", "")
        log_actividad("FEEDBACK", f"{feedback_type}: {message[:50]}")

        feedback = cargar_feedback()
        if feedback_type == "positive":
            feedback["aprobados"].append(
                {"message": message, "timestamp": datetime.now().isoformat()}
            )
        else:
            feedback["rechazados"].append(
                {"message": message, "timestamp": datetime.now().isoformat()}
            )

        guardar_feedback(feedback)
        return jsonify({"ok": True, "message": "Feedback recibido"})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json()
    mensaje = data.get("message", "")
    try:
        resp = requests.post("http://localhost:5052/chat", json={"message": mensaje}, timeout=30)
        resp.raise_for_status()
        respuesta = resp.json().get("response", "No se pudo obtener respuesta.")
        modelo_usado = resp.json().get("model_used", "desconocido")
        print(f"[{modelo_usado}] {mensaje[:50]}...")
    except Exception as e:
        respuesta = f"Error en el enrutador: {str(e)}"
    return jsonify({"respuesta": respuesta})


def _check_code_health() -> str | None:
    """Verifica proactivamente si hay errores recurrentes nuevos. Retorna mensaje o None."""
    try:
        new_patterns = code_assistant.analyze_logs("ura.log")
        if new_patterns:
            recurrent = [p for p in new_patterns if p.count >= code_assistant.threshold]
            if recurrent:
                pattern_names = ", ".join(p.pattern[:60] for p in recurrent[:3])
                return f"⚠️ He detectado {len(recurrent)} errores recurrentes: {pattern_names}...\n\n¿Quieres que proponga mejoras automáticas? Responde 'revisar errores' para ver el detalle."

        pending = code_assistant.get_pending_improvements()
        if pending:
            return f"💡 Tengo {len(pending)} mejoras de código pendientes de tu aprobación. Escribe 'revisar errores' para verlas."
    except Exception as e:
        logger.error(f"Error en _check_code_health: {e}")
    return None


def _route_command(message: str) -> dict | None:
    """Enruta comandos especiales del usuario. Retorna respuesta o None si no es comando."""
    msg = message.lower().strip()

    # --- AYUDA ---
    if any(kw in msg for kw in ["¿qué puedes hacer", "ayuda", "help", "comandos", "capacidades"]):
        return {
            "ok": True,
            "response": _get_help_text(),
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }

    # --- AGENTE AUTÓNOMO ---
    action_id = None
    if any(
        kw in msg for kw in ["limpia el escritorio", "limpiar escritorio", "ordenar escritorio"]
    ):
        action_id = "clean_desktop"
    elif msg.startswith("investiga ") or msg.startswith("investigar "):
        topic = msg.replace("investiga ", "", 1).replace("investigar ", "", 1).strip()
        if topic:
            result = research_pipeline.execute(topic)
            _last_research_report["topic"] = topic
            _last_research_report["full_report"] = result["full_report"]
            return {
                "ok": True,
                "response": result["executive_summary"]
                + "\n\n_Escribe 'informe completo' o 'más detalles' para ver el informe detallado._",
                "meta_confidence": 1.0,
                "value_score": 1.0,
                "full_report": result["full_report"],
            }
    elif msg in ("estado de los sandboxes", "estado sandboxes", "sandboxes status"):
        status = sandbox_orchestrator.get_all_status()
        lines = [f"**Sandboxes** (acelerado: {status['accelerated_active']}):"]
        for sid, sb in status["sandboxes"].items():
            lines.append(
                f"• **{sid}** ({sb['location']}): {sb['status']} — última: {sb.get('last_run', 'nunca')}"
            )
        lines.append(
            f"\nCiclo normal: {status['cycle_normal_seconds']}s | Acelerado: {status['cycle_accelerated_seconds']}s"
        )
        return {
            "ok": True,
            "response": "\n".join(lines),
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }
    elif msg in ("activar ciclo acelerado", "acelera ciclo", "ciclo acelerado"):
        result = sandbox_orchestrator.trigger_accelerated_cycle(reason="comando manual desde chat")
        return {
            "ok": True,
            "response": result.get("message", "Activado"),
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }
    elif msg in (
        "¿qué sandbox está fallando?",
        "que sandbox esta fallando",
        "sandboxes con errores",
    ):
        failing = sandbox_orchestrator.get_failing_sandboxes()
        if not failing:
            return {
                "ok": True,
                "response": "✅ Ningún sandbox está fallando.",
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }
        lines = ["❌ Sandboxes con errores:"]
        for sb in failing:
            lines.append(
                f"• **{sb['id']}**: {sb.get('status')} — última: {sb.get('last_run', 'nunca')}"
            )
        return {
            "ok": True,
            "response": "\n".join(lines),
            "meta_confidence": 1.0,
            "value_score": 0.5,
        }
    elif msg.startswith("vocabulario de "):
        dept = msg.replace("vocabulario de ", "", 1).strip()
        vocab = vocabulary_manager.get_vocabulary(dept)
        if vocab:
            terms_list = "\n".join(
                f"• **{t}**: {(e.get('definition', '') if isinstance(e, dict) else str(e))[:120]}"
                for t, e in list(vocab.terms.items())[:20]
            )
            return {
                "ok": True,
                "response": f"**Vocabulario de {dept}** ({len(vocab.terms)} términos, sinónimos: {vocab.allow_synonyms}):\n\n{terms_list}",
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }
        return {
            "ok": True,
            "response": f"Departamento '{dept}' no encontrado.",
            "meta_confidence": 1.0,
            "value_score": 0.5,
        }
    elif msg.startswith("añade término ") or msg.startswith("anade termino "):
        # Formato: "añade término X a Y: definición"
        try:
            body = msg.replace("añade término ", "", 1).replace("anade termino ", "", 1)
            term_part, definition = body.split(":", 1)
            term, _, dept = term_part.partition(" a ")
            term = term.strip()
            dept = dept.strip()
            definition = definition.strip()
            vocab = vocabulary_manager.get_vocabulary(dept)
            if vocab:
                vocab.add_term(term, definition, source="chat")
                from pathlib import Path as _P

                vocab.save_to_file(_P.home() / ".ura" / "vocabulary" / f"{dept}.json")
                return {
                    "ok": True,
                    "response": f"✅ Término '{term}' añadido a {dept}.",
                    "meta_confidence": 1.0,
                    "value_score": 1.0,
                }
            return {
                "ok": True,
                "response": f"Departamento '{dept}' no encontrado.",
                "meta_confidence": 1.0,
                "value_score": 0.5,
            }
        except Exception as e:
            return {
                "ok": True,
                "response": f"Formato: 'añade término X a Y: definición'. Error: {e}",
                "meta_confidence": 1.0,
                "value_score": 0.3,
            }
    elif msg in ("informe completo", "más detalles", "mas detalles", "detalles completos"):
        if _last_research_report.get("full_report"):
            return {
                "ok": True,
                "response": _last_research_report["full_report"],
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }
        else:
            return {
                "ok": True,
                "response": "No hay ningún informe reciente. Escribe 'investiga <tema>' primero.",
                "meta_confidence": 1.0,
                "value_score": 0.5,
            }
    elif msg.startswith("instala ") or msg.startswith("instalar "):
        pkg = msg.replace("instala ", "", 1).replace("instalar ", "", 1).strip()
        if pkg:
            version = None
            if "==" in pkg:
                pkg, version = pkg.split("==", 1)
            result = conflict_detector.analyze_installation(pkg.strip(), version)
            return {
                "ok": True,
                "response": result.get("message", "")
                + (
                    f"\n\nConflictos: {len(result.get('conflicts', []))}"
                    if result.get("conflicts")
                    else ""
                ),
                "meta_confidence": 1.0,
                "value_score": 1.0 if result.get("applied") else 0.3,
            }
    elif any(
        kw in msg for kw in ["organiza descargas", "organizar descargas", "ordenar descargas"]
    ):
        action_id = "organize_downloads"
    elif any(kw in msg for kw in ["vaciar papelera", "vacía la papelera", "vacía papelera"]):
        action_id = "empty_trash"
    elif any(
        kw in msg for kw in ["eliminar duplicados", "elimina duplicados", "borrar duplicados"]
    ):
        action_id = "remove_duplicates"
    elif any(
        kw in msg for kw in ["crear backup", "hacer backup", "backup manual", "copia de seguridad"]
    ):
        action_id = "create_backup"

    if action_id:
        # Validar con sistema de valores primero
        value_check = value_system.evaluate_action(f"Ejecutar acción autónoma: {action_id}")
        if value_check.get("recommendation") == "reject":
            return {
                "ok": True,
                "response": f"🚫 Acción bloqueada por sistema de valores: {value_check.get('reason', 'No cumple los criterios éticos')}",
                "meta_confidence": 1.0,
                "value_score": 0.0,
            }

        result = autonomous_agent.request_action(action_id)
        if "error" in result:
            return {
                "ok": True,
                "response": f"❌ {result['error']}",
                "meta_confidence": 1.0,
                "value_score": 0.0,
            }
        if result.get("requires_confirmation"):
            # Iniciar verificación dual (biometría + push)
            auth = dual_verification.request_authorization(f"Ejecutar: {action_id}")
            if auth:
                confirmed = autonomous_agent.confirm_action(action_id, True)
                return {
                    "ok": True,
                    "response": f"✅ Verificación dual superada. Acción ejecutada: {confirmed.get('action', action_id)}",
                    "meta_confidence": 1.0,
                    "value_score": 1.0,
                }
            else:
                return {
                    "ok": True,
                    "response": "🚫 Verificación dual fallida. Acción cancelada.",
                    "meta_confidence": 1.0,
                    "value_score": 0.5,
                }
        return {
            "ok": True,
            "response": f"✅ Acción ejecutada: {result.get('action', action_id)}",
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }

    # --- CONFIRMACIÓN DE ACCIÓN PENDIENTE ---
    if msg in ["sí", "si", "confirmar", "confirma", "ok", "dale", "adelante"]:
        pending = autonomous_agent.get_pending_confirmations()
        if pending:
            action = pending[0]
            result = autonomous_agent.confirm_action(action.id, True)
            return {
                "ok": True,
                "response": f"✅ Acción confirmada y ejecutada: {result.get('action', action.id)}",
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }

    if msg in ["no", "cancelar", "cancela", "nop", "nope"]:
        pending = autonomous_agent.get_pending_confirmations()
        if pending:
            action = pending[0]
            autonomous_agent.confirm_action(action.id, False)
            return {
                "ok": True,
                "response": "🚫 Acción cancelada.",
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }

    # --- APPLE INTEGRATION ---
    if any(kw in msg for kw in ["calendario hoy", "eventos hoy", "qué tengo hoy", "agenda hoy"]):
        try:
            summary = apple_integration.get_today_summary()
            events = summary.get("events", [])
            reminders = summary.get("reminders", [])
            parts = ["📅 **Tu día de hoy:**\n"]
            if events:
                parts.append("**Eventos:**")
                for e in events:
                    parts.append(f"  • {e.get('title', 'Sin título')} — {e.get('start_date', '?')}")
            else:
                parts.append("**Eventos:** Ninguno")
            if reminders:
                parts.append("\n**Recordatorios pendientes:**")
                for r in reminders:
                    parts.append(f"  • {r.get('title', 'Sin título')}")
            else:
                parts.append("\n**Recordatorios:** Ninguno pendiente")
            return {
                "ok": True,
                "response": "\n".join(parts),
                "meta_confidence": 1.0,
                "value_score": 1.0,
            }
        except Exception as e:
            return {
                "ok": True,
                "response": f"❌ Error consultando calendario: {e}",
                "meta_confidence": 0.5,
                "value_score": 0.5,
            }

    if (
        "añade un recordatorio" in msg
        or "crea un recordatorio" in msg
        or "nuevo recordatorio" in msg
    ):
        return {
            "ok": True,
            "response": "📝 Para crear un recordatorio, dime el título y la fecha. Ejemplo: 'recordatorio: comprar pan, mañana 10:00'",
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }

    if "crea una nota" in msg or "nueva nota" in msg or "añade una nota" in msg:
        return {
            "ok": True,
            "response": "📝 Para crear una nota, dime el título y el contenido. Ejemplo: 'nota: ideas para el restaurante, contenido: probar nuevo menú degustación'",
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }

    # --- CODE ASSISTANT ---
    if any(
        kw in msg
        for kw in ["errores recurrentes", "errores detectados", "revisar errores", "código roto"]
    ):
        summary = code_assistant.get_error_summary()
        pending_improvements = code_assistant.get_pending_improvements()
        parts = ["🔍 **Asistente de Código:**\n"]
        parts.append(f"• Patrones de error: {summary.get('total_patterns', 0)}")
        parts.append(f"• Errores recurrentes: {summary.get('recurrent_patterns', 0)}")
        parts.append(f"• Mejoras pendientes: {summary.get('pending_improvements', 0)}")
        parts.append(f"• Mejoras aplicadas: {summary.get('applied_improvements', 0)}")
        if pending_improvements:
            parts.append(
                f"\n⚠️ Hay {len(pending_improvements)} mejoras pendientes. ¿Quieres que las revise?"
            )
        return {
            "ok": True,
            "response": "\n".join(parts),
            "meta_confidence": 1.0,
            "value_score": 1.0,
        }

    return None


def _get_help_text() -> str:
    """Genera el texto de ayuda con todas las capacidades de URA."""
    return """🤖 **URA — Capacidades disponibles:**

**💬 Chat inteligente:**
• Respondo preguntas sobre hostelería, finanzas, sistema y más
• Memoria caché para respuestas rápidas
• Validación ética de respuestas con sistema de valores

**🧹 Agente Autónomo:**
• \"limpia el escritorio\" — Organiza archivos del escritorio
• \"organiza descargas\" — Clasifica archivos por tipo
• \"vaciar papelera\" — Vacía la papelera (requiere confirmación)
• \"eliminar duplicados\" — Borra archivos duplicados en Downloads
• \"crear backup manual\" — Copia de seguridad de ~/.ura/

**📅 Integración Apple:**
• \"¿qué tengo en el calendario hoy?\" — Eventos y recordatorios
• \"crea un recordatorio...\" — Añadir recordatorio
• \"crea una nota...\" — Añadir nota

**🔧 Asistente de Código:**
• \"revisar errores\" — Ver errores recurrentes detectados
• Propone mejoras automáticas con OpenCode

**📊 Monitorización:**
• Dashboard en /dashboard — Métricas CPU, RAM, Disco
• /health — Estado de servicios (Ollama, OpenClaw)
• /api/metrics — API JSON de métricas

**🧪 Tests:**
• 26 tests unitarios y de integración
• Ejecutar con: python -m pytest tests/ -q

**🔐 Seguridad:**
• Verificación biométrica (Touch ID)
• Notificaciones push (Pushover)
• Registro en ~/.ura/security.log

**🔍 Análisis Forense:**
• Registro de 1000 eventos del sistema
• Detección de detonantes de errores
• Cruce de patrones y predicción de problemas
• /api/forensic/status — Estado del escribiente

**🔄 Sincronización:**
• iCloud sync cada hora (~/.ura/ ↔ iCloud Drive)
• Manejo de conflictos por timestamp"""


def inferir_dominio(mensaje: str) -> str:
    """Infiere el dominio de conocimiento a partir del mensaje."""
    mensaje_lower = mensaje.lower()

    dominios = {
        "hostelería": [
            "restaurante",
            "bar",
            "camarero",
            "cocina",
            "menú",
            "carta",
            "cliente",
            "reserva",
        ],
        "finanzas": ["dinero", "precio", "coste", "beneficio", "pérdida", "impuesto", "factura"],
        "sistema": ["ordenador", "disco", "memoria", "programa", "archivo", "carpeta", "instalar"],
        "personal": ["ramón", "empleado", "jefe", "equipo", "trabajo"],
        "inventario": ["producto", "stock", "existencias", "almacén", "pedido"],
    }

    for dominio, keywords in dominios.items():
        if any(kw in mensaje_lower for kw in keywords):
            return dominio

    return "general"


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5050, debug=False)
