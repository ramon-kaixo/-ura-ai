#!/usr/bin/env python3
"""
AGENTE VIGILANTE — Monitoriza servicios y alerta si algo cae.

Vigila continuamente:
- Servicios systemd (Ollama, Model Router, etc.)
- Puertos de red (11434, 11435, 9092, etc.)
- Uso de CPU, RAM y disco
- Conectividad de red (Thunderbolt, Tailscale)
- Procesos críticos

Alerta via Telegram y registra en board.db cuando detecta problemas.
"""

import json
import logging
import os
import sqlite3
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SISTEMA = Path(__file__).parent.parent
LOG_DIR = SISTEMA / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG = LOG_DIR / "vigilante.log"
DB_PATH = SISTEMA / "board.db"

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

SERVICIOS_MONITORIZADOS = [
    {"nombre": "ollama", "tipo": "systemd", "critico": True},
    {"nombre": "model-router", "tipo": "systemd", "critico": True},
    {"nombre": "ura-network", "tipo": "systemd", "critico": False},
]

PUERTOS_MONITORIZADOS = [
    {"puerto": 11434, "servicio": "Ollama", "host": "localhost", "critico": True},
    {"puerto": 11435, "servicio": "Model Router", "host": "localhost", "critico": True},
]

ENDPOINTS_MONITORIZADOS = [
    {"url": "http://localhost:11434/api/tags", "nombre": "Ollama API", "critico": True},
    {"url": "http://localhost:11435/health", "nombre": "Model Router Health", "critico": True},
]

HOSTS_MONITORIZADOS = [
    {"host": "10.164.1.17", "nombre": "Mac Mini (Thunderbolt)", "critico": False},
]

UMBRALES = {
    "cpu_pct": 90,
    "ram_pct": 85,
    "disco_pct": 90,
    "swap_pct": 80,
}


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    logger.info(msg)


def _run(cmd: str, timeout: int = 10) -> dict:
    try:
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
        return {
            "ok": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
        }
    except Exception as e:
        return {"ok": False, "stdout": "", "stderr": str(e)}


class AgenteVigilante:
    """Monitoriza servicios y alerta cuando algo cae."""

    def __init__(self) -> None:
        self.alertas_enviadas: dict[str, float] = {}
        self.cooldown_alertas = 300  # 5 minutos entre alertas repetidas
        self._init_db()

    def _init_db(self) -> None:
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vigilante_alertas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    servicio TEXT NOT NULL,
                    tipo TEXT NOT NULL,
                    mensaje TEXT NOT NULL,
                    severidad TEXT NOT NULL,
                    resuelta INTEGER DEFAULT 0
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vigilante_estado (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cpu_pct REAL,
                    ram_pct REAL,
                    disco_pct REAL,
                    servicios_ok INTEGER,
                    servicios_total INTEGER,
                    alertas_activas INTEGER
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            _log(f"Error inicializando DB: {e}")

    def verificar_servicios_systemd(self) -> list[dict]:
        """Verifica el estado de servicios systemd."""
        resultados = []
        for svc in SERVICIOS_MONITORIZADOS:
            check = _run(f"systemctl is-active {svc['nombre']}")
            estado = check["stdout"] if check["ok"] else "unknown"
            activo = estado == "active"

            resultado = {
                "servicio": svc["nombre"],
                "estado": estado,
                "activo": activo,
                "critico": svc["critico"],
            }

            if not activo and svc["critico"]:
                self._registrar_alerta(
                    svc["nombre"],
                    "servicio_caido",
                    f"Servicio {svc['nombre']} está {estado}",
                    "critica",
                )
                resultado["accion"] = self._intentar_reinicio(svc["nombre"])

            resultados.append(resultado)

        return resultados

    def verificar_puertos(self) -> list[dict]:
        """Verifica que los puertos esperados estén escuchando."""
        resultados = []
        for port_info in PUERTOS_MONITORIZADOS:
            check = _run(f"ss -tlnp | grep :{port_info['puerto']}")
            escuchando = check["ok"] and str(port_info["puerto"]) in check["stdout"]

            resultado = {
                "puerto": port_info["puerto"],
                "servicio": port_info["servicio"],
                "escuchando": escuchando,
                "critico": port_info["critico"],
            }

            if not escuchando and port_info["critico"]:
                self._registrar_alerta(
                    port_info["servicio"],
                    "puerto_cerrado",
                    f"Puerto {port_info['puerto']} ({port_info['servicio']}) no escucha",
                    "alta",
                )

            resultados.append(resultado)

        return resultados

    def verificar_endpoints(self) -> list[dict]:
        """Verifica que los endpoints HTTP respondan."""
        resultados = []
        for ep in ENDPOINTS_MONITORIZADOS:
            try:
                req = Request(ep["url"])
                with urlopen(req, timeout=5) as resp:
                    status = resp.status
                    body = resp.read().decode()
                    respondiendo = 200 <= status < 500
            except Exception:
                status = 0
                body = ""
                respondiendo = False

            resultado = {
                "endpoint": ep["url"],
                "nombre": ep["nombre"],
                "respondiendo": respondiendo,
                "status": status,
                "critico": ep["critico"],
            }

            if not respondiendo and ep["critico"]:
                self._registrar_alerta(
                    ep["nombre"],
                    "endpoint_caido",
                    f"Endpoint {ep['nombre']} ({ep['url']}) no responde",
                    "critica",
                )

            resultados.append(resultado)

        return resultados

    def verificar_recursos(self) -> dict:
        """Verifica CPU, RAM y disco."""
        recursos = {}

        cpu = _run(
            "grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {printf \"%.1f\", usage}'"
        )
        recursos["cpu_pct"] = float(cpu["stdout"]) if cpu["ok"] and cpu["stdout"] else 0

        mem = _run("free | awk '/Mem:/ {printf \"%.1f\", $3/$2*100}'")
        recursos["ram_pct"] = float(mem["stdout"]) if mem["ok"] and mem["stdout"] else 0

        mem_detail = _run("free -m | awk '/Mem:/ {printf \"%d/%d\", $3, $2}'")
        recursos["ram_detalle"] = mem_detail["stdout"] if mem_detail["ok"] else "?"

        disco = _run("df / | awk 'NR==2 {printf \"%.1f\", $5}'")
        recursos["disco_pct"] = (
            float(disco["stdout"].replace("%", "")) if disco["ok"] and disco["stdout"] else 0
        )

        for recurso, umbral in UMBRALES.items():
            valor = recursos.get(recurso, 0)
            if valor > umbral:
                self._registrar_alerta(
                    recurso,
                    "recurso_alto",
                    f"{recurso} al {valor}% (umbral: {umbral}%)",
                    "alta",
                )

        return recursos

    def verificar_conectividad(self) -> list[dict]:
        """Verifica conectividad a hosts monitorizados."""
        resultados = []
        for host in HOSTS_MONITORIZADOS:
            check = _run(f"ping -c 1 -W 2 {host['host']}")
            alcanzable = check["ok"]

            latencia = None
            if alcanzable and "time=" in check["stdout"]:
                import re

                match = re.search(r"time=(\d+\.?\d*)", check["stdout"])
                if match:
                    latencia = float(match.group(1))

            resultados.append(
                {
                    "host": host["host"],
                    "nombre": host["nombre"],
                    "alcanzable": alcanzable,
                    "latencia_ms": latencia,
                }
            )

        return resultados

    def _intentar_reinicio(self, servicio: str) -> dict:
        """Intenta reiniciar un servicio caído."""
        _log(f"Intentando reiniciar: {servicio}")
        result = _run(f"sudo systemctl restart {servicio}")
        if result["ok"]:
            time.sleep(3)
            check = _run(f"systemctl is-active {servicio}")
            if check["stdout"] == "active":
                _log(f"Reinicio exitoso: {servicio}")
                self._enviar_telegram(f"🔄 Servicio {servicio} reiniciado automáticamente")
                return {"reiniciado": True}

        _log(f"Reinicio fallido: {servicio}")
        self._enviar_telegram(f"🚨 Servicio {servicio} NO se pudo reiniciar")
        return {"reiniciado": False, "error": result["stderr"]}

    def _registrar_alerta(self, servicio: str, tipo: str, mensaje: str, severidad: str) -> None:
        """Registra una alerta en la BD y envía notificación."""
        clave = f"{servicio}:{tipo}"
        ahora = time.time()

        if clave in self.alertas_enviadas:
            if ahora - self.alertas_enviadas[clave] < self.cooldown_alertas:
                return

        self.alertas_enviadas[clave] = ahora
        _log(f"ALERTA [{severidad}] {servicio}: {mensaje}")

        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                "INSERT INTO vigilante_alertas (timestamp, servicio, tipo, mensaje, severidad) VALUES (?, ?, ?, ?, ?)",
                (datetime.now().isoformat(), servicio, tipo, mensaje, severidad),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            _log(f"Error guardando alerta: {e}")

        if severidad in ("critica", "alta"):
            self._enviar_telegram(f"⚠️ [{severidad.upper()}] {servicio}: {mensaje}")

    def _enviar_telegram(self, mensaje: str) -> None:
        """Envía notificación por Telegram."""
        if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
            _log(f"Telegram no configurado. Mensaje: {mensaje}")
            return

        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            data = json.dumps(
                {"chat_id": TELEGRAM_CHAT_ID, "text": mensaje, "parse_mode": "HTML"}
            ).encode()
            req = Request(url, data=data, headers={"Content-Type": "application/json"})
            urlopen(req, timeout=10)
            _log(f"Telegram enviado: {mensaje[:50]}")
        except Exception as e:
            _log(f"Error enviando Telegram: {e}")

    def _guardar_estado(
        self, recursos: dict, servicios_ok: int, servicios_total: int, alertas: int
    ) -> None:
        """Guarda el estado actual en la BD."""
        try:
            conn = sqlite3.connect(DB_PATH)
            conn.execute(
                """INSERT INTO vigilante_estado (timestamp, cpu_pct, ram_pct, disco_pct, servicios_ok, servicios_total, alertas_activas)
                VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().isoformat(),
                    recursos.get("cpu_pct", 0),
                    recursos.get("ram_pct", 0),
                    recursos.get("disco_pct", 0),
                    servicios_ok,
                    servicios_total,
                    alertas,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            _log(f"Error guardando estado: {e}")

    def ejecutar_chequeo(self) -> dict:
        """Ejecuta un chequeo completo."""
        _log("Iniciando chequeo completo...")

        servicios = self.verificar_servicios_systemd()
        puertos = self.verificar_puertos()
        endpoints = self.verificar_endpoints()
        recursos = self.verificar_recursos()
        conectividad = self.verificar_conectividad()

        servicios_ok = sum(1 for s in servicios if s["activo"])
        servicios_total = len(servicios)
        alertas_activas = sum(1 for s in servicios if not s["activo"] and s["critico"])
        alertas_activas += sum(1 for p in puertos if not p["escuchando"] and p["critico"])
        alertas_activas += sum(1 for e in endpoints if not e["respondiendo"] and e["critico"])

        self._guardar_estado(recursos, servicios_ok, servicios_total, alertas_activas)

        resultado = {
            "timestamp": datetime.now().isoformat(),
            "servicios": servicios,
            "puertos": puertos,
            "endpoints": endpoints,
            "recursos": recursos,
            "conectividad": conectividad,
            "resumen": {
                "servicios": f"{servicios_ok}/{servicios_total} activos",
                "alertas_activas": alertas_activas,
                "estado_general": "OK" if alertas_activas == 0 else "ALERTA",
            },
        }

        estado = resultado["resumen"]["estado_general"]
        _log(
            f"Chequeo completo: {estado} ({servicios_ok}/{servicios_total} servicios, {alertas_activas} alertas)"
        )

        return resultado

    def ejecutar(self, tarea: str = "chequeo", **kwargs) -> dict:
        """Punto de entrada principal."""
        if tarea == "chequeo":
            return self.ejecutar_chequeo()
        elif tarea == "servicios":
            return {"servicios": self.verificar_servicios_systemd()}
        elif tarea == "recursos":
            return {"recursos": self.verificar_recursos()}
        elif tarea == "conectividad":
            return {"conectividad": self.verificar_conectividad()}

        return {"error": f"Tarea desconocida: {tarea}"}


def ejecutar(tarea: str = "chequeo", **kwargs) -> dict:
    """Función de entrada para el orquestador."""
    agente = AgenteVigilante()
    return agente.ejecutar(tarea, **kwargs)


if __name__ == "__main__":
    import sys

    tarea = sys.argv[1] if len(sys.argv) > 1 else "chequeo"
    resultado = ejecutar(tarea)
    print(json.dumps(resultado, indent=2, default=str, ensure_ascii=False))
