#!/usr/bin/env python3
"""
Revisión Semanal Automática de Herramientas - URA App
Revisa herramientas, puntúa 0-100, analiza tendencias y activa auto-healing si hay degradación.
"""

import json
import logging
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent
SCORES_FILE = ROOT / "data" / "tool_health_scores.json"
REPORT_FILE = ROOT / "logs" / "reporte_semanal.json"
LOG_FILE = ROOT / "logs" / "revision_semanal.log"

UMBRAL_ALERTA = 60  # por debajo → alerta
UMBRAL_FALLBACK = 30  # por debajo → cambiar a backup automáticamente
UMBRAL_DEGRADACION = 10  # caída de 10+ puntos en tendencia → auto-healing


# ── helpers ──────────────────────────────────────────────────────────────────


def _log(msg: str, nivel: str = "INFO") -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    with LOG_FILE.open("a") as f:
        f.write(f"{datetime.now().isoformat()} - {nivel} - {msg}\n")
    logger.log(getattr(logging, nivel), msg)


def _port_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _run(cmd: list[str], timeout: int = 10) -> bool:
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=timeout)
        return r.returncode == 0
    except Exception:
        return False


# ── puntuadores por herramienta ───────────────────────────────────────────────


def _score_ollama() -> int:
    score = 0
    if _port_open("localhost", 11434):
        score += 50
    if _run(["ollama", "list"], timeout=15):
        score += 30
    # bonus: responde a API
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=3) as r:  # nosec B310
            if r.status == 200:
                score += 20
    except Exception:
        pass
    return min(score, 100)


def _score_redis() -> int:
    score = 0
    if _port_open("localhost", 6379):
        score += 50
    try:
        import redis as redis_lib

        r = redis_lib.Redis(host="localhost", port=6379, socket_timeout=2)
        r.ping()
        score += 30
        r.set("_ura_health_check", "1", ex=5)
        if r.get("_ura_health_check"):
            score += 20
    except Exception:
        pass
    return min(score, 100)


def _score_docker() -> int:
    score = 0
    if _run(["docker", "ps"], timeout=10):
        score += 60
    try:
        r = subprocess.run(
            ["docker", "ps", "--format", "{{.Names}}"], capture_output=True, text=True, timeout=10
        )
        containers = r.stdout.strip().splitlines()
        ura_containers = [c for c in containers if "ura" in c.lower() or "n8n" in c.lower()]
        score += min(len(ura_containers) * 10, 40)
    except Exception:
        pass
    return min(score, 100)


def _score_n8n() -> int:
    score = 0
    if _port_open("localhost", 5678):
        score += 70
    try:
        import urllib.request

        with urllib.request.urlopen("http://localhost:5678/healthz", timeout=3) as r:  # nosec B310
            if r.status == 200:
                score += 30
    except Exception:
        pass
    return min(score, 100)


def _score_disk() -> int:
    try:
        import psutil

        d = psutil.disk_usage("/")
        libre_pct = 100 - d.percent
        return max(0, min(100, int(libre_pct * 1.5)))
    except Exception:
        return 50


def _score_ram() -> int:
    try:
        import psutil

        m = psutil.virtual_memory()
        libre_pct = 100 - m.percent
        return max(0, min(100, int(libre_pct * 1.5)))
    except Exception:
        return 50


HERRAMIENTAS: dict[str, Any] = {
    "ollama": {"nombre": "Ollama (IA local)", "scorer": _score_ollama, "fallback": "OpenAI API"},
    "redis": {"nombre": "Redis (caché)", "scorer": _score_redis, "fallback": "Memoria local"},
    "docker": {
        "nombre": "Docker (contenedores)",
        "scorer": _score_docker,
        "fallback": "Procesos directos",
    },
    "n8n": {"nombre": "n8n (automatización)", "scorer": _score_n8n, "fallback": "Cron manual"},
    "disco": {"nombre": "Disco libre", "scorer": _score_disk, "fallback": "Limpieza automática"},
    "ram": {"nombre": "RAM disponible", "scorer": _score_ram, "fallback": "Modelo más ligero"},
}


# ── carga / guarda histórico ───────────────────────────────────────────────────


def _load_scores() -> dict:
    if SCORES_FILE.exists():
        try:
            return json.loads(SCORES_FILE.read_text())
        except Exception:
            return {}
    return {}


def _save_scores(scores: dict) -> None:
    SCORES_FILE.parent.mkdir(parents=True, exist_ok=True)
    SCORES_FILE.write_text(json.dumps(scores, indent=2, ensure_ascii=False))


# ── revisión principal ─────────────────────────────────────────────────────────


def _analizar_tendencia(historico: list) -> dict:
    """
    Analiza la tendencia de puntuaciones históricas

    Args:
        historico: Lista de puntuaciones históricas

    Returns:
        Dict con información de tendencia
    """
    if len(historico) < 3:
        return {"degradacion": False, "cambio": 0, "tendencia": "insuficiente_datos"}

    # Obtener últimas 4 semanas
    ultimas_4 = [h["score"] for h in historico[-4:]]

    # Calcular cambio promedio entre semanas consecutivas
    cambios = []
    for i in range(1, len(ultimas_4)):
        cambios.append(ultimas_4[i] - ultimas_4[i - 1])

    cambio_promedio = sum(cambios) / len(cambios) if cambios else 0

    # Detectar degradación
    degradacion = cambio_promedio < -UMBRAL_DEGRADACION

    if degradacion:
        tendencia = "degradacion"
    elif cambio_promedio > UMBRAL_DEGRADACION:
        tendencia = "mejora"
    else:
        tendencia = "estable"

    return {
        "degradacion": degradacion,
        "cambio": round(cambio_promedio, 2),
        "tendencia": tendencia,
        "ultimas_4": ultimas_4,
    }


def _activar_auto_healing(herramienta: str) -> bool:
    """
    Activa auto-healing para una herramienta degradada

    Args:
        herramienta: Nombre de la herramienta

    Returns:
        True si se activó auto-healing correctamente
    """
    try:
        from core.auto_healing import intentar_recuperacion

        _log(f"Activando auto-healing para {herramienta}", "INFO")
        recuperado = intentar_recuperacion(herramienta)

        if recuperado:
            _log(f"Auto-healing exitoso para {herramienta}", "INFO")
        else:
            _log(f"Auto-healing falló para {herramienta}", "ERROR")

        return recuperado
    except Exception as e:
        _log(f"Error activando auto-healing: {e}", "ERROR")
        return False


class RevisionSemanal:
    """Gestor de revisión semanal con puntuación 0-100, análisis de tendencia y auto-healing."""

    def __init__(self):
        self.scores_historico = _load_scores()

    def ejecutar_revision_completa(self) -> dict:
        _log("=" * 60)
        _log("INICIANDO REVISIÓN SEMANAL")
        _log("=" * 60)

        timestamp = datetime.now().isoformat()
        resultados: dict = {
            "timestamp": timestamp,
            "herramientas": {},
            "alertas": [],
            "acciones": [],
            "tendencias": {},
        }

        for tool_id, info in HERRAMIENTAS.items():
            score = info["scorer"]()
            nombre = info["nombre"]
            fallback = info["fallback"]

            # Analizar tendencia si hay histórico suficiente
            tendencia = {"tendencia": "sin_datos"}
            if tool_id in self.scores_historico and len(self.scores_historico[tool_id]) >= 3:
                tendencia = _analizar_tendencia(self.scores_historico[tool_id])
                resultados["tendencias"][tool_id] = tendencia

                # Si hay degradación, activar auto-healing
                if tendencia["degradacion"]:
                    msg = f"📉 {nombre}: degradación detectada (cambio: {tendencia['cambio']})"
                    _log(msg, "WARNING")
                    resultados["alertas"].append(
                        {
                            "nivel": "degradacion",
                            "herramienta": tool_id,
                            "score": score,
                            "cambio": tendencia["cambio"],
                        }
                    )

                    # Activar auto-healing
                    recuperado = _activar_auto_healing(tool_id)
                    if recuperado:
                        resultados["acciones"].append(f"Auto-healing exitoso: {nombre}")
                    else:
                        resultados["acciones"].append(f"Auto-healing falló: {nombre}")

            resultado = {
                "nombre": nombre,
                "score": score,
                "fallback": fallback,
                "accion": "ok",
                "timestamp": timestamp,
                "tendencia": tendencia["tendencia"],
            }

            if score < UMBRAL_FALLBACK:
                msg = f"🔴 {nombre}: {score}/100 — CRÍTICO, activando fallback → {fallback}"
                _log(msg, "ERROR")
                resultados["alertas"].append(
                    {"nivel": "critico", "herramienta": tool_id, "score": score}
                )
                resultados["acciones"].append(f"Fallback activado: {nombre} → {fallback}")
                resultado["accion"] = "fallback"
            elif score < UMBRAL_ALERTA:
                msg = f"🟡 {nombre}: {score}/100 — DEGRADADO, monitorizar"
                _log(msg, "WARNING")
                if not tendencia.get("degradacion", False):  # Solo alertar si no es degradación
                    resultados["alertas"].append(
                        {"nivel": "alerta", "herramienta": tool_id, "score": score}
                    )
                resultado["accion"] = "alerta"
            else:
                _log(f"🟢 {nombre}: {score}/100 — OK (tendencia: {tendencia['tendencia']})")

            # guardar histórico por herramienta
            if tool_id not in self.scores_historico:
                self.scores_historico[tool_id] = []
            self.scores_historico[tool_id].append({"fecha": timestamp, "score": score})
            # conservar solo las últimas 52 semanas
            self.scores_historico[tool_id] = self.scores_historico[tool_id][-52:]

            resultados["herramientas"][tool_id] = resultado

        _save_scores(self.scores_historico)

        REPORT_FILE.parent.mkdir(parents=True, exist_ok=True)
        REPORT_FILE.write_text(json.dumps(resultados, indent=2, ensure_ascii=False))

        _log(
            f"REVISIÓN COMPLETADA — alertas: {len(resultados['alertas'])}, acciones: {len(resultados['acciones'])}"
        )
        return resultados


if __name__ == "__main__":
    rev = RevisionSemanal()
    resultado = rev.ejecutar_revision_completa()
    print("\n=== REVISIÓN SEMANAL ===")
    for tid, r in resultado["herramientas"].items():
        icon = (
            "🟢"
            if r["score"] >= UMBRAL_ALERTA
            else ("🟡" if r["score"] >= UMBRAL_FALLBACK else "🔴")
        )
        print(f"{icon} {r['nombre']}: {r['score']}/100")
    if resultado["alertas"]:
        print(f"\n⚠️  {len(resultado['alertas'])} alertas generadas")
    if resultado["acciones"]:
        print(f"🔧 Acciones tomadas: {resultado['acciones']}")
