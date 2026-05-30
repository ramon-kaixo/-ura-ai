#!/usr/bin/env python3
"""
URA — Agente de Red y Telefonía

Gestión autónoma de WiFi, router (Movistar/Telefónica) y datos móviles.
Usa core.ejecutor_seguro para todos los comandos shell, de modo que
la lista negra centralizada bloquea automáticamente comandos peligrosos.
"""

import logging
import time
import urllib.request
from pathlib import Path

import requests

from core.ejecutor_seguro import ejecutar

# scrub() es opcional: si privacy_scrubber expone un helper top-level lo
# usamos, si no existe (caso actual del repo) caemos a un no-op silencioso.
try:
    from core.privacy_scrubber import scrub  # type: ignore[attr-defined]
except ImportError:

    def scrub(texto: str) -> str:  # type: ignore[no-redef]
        return texto


logger = logging.getLogger(__name__)


class AgenteRedTelefonia:
    """Gestión autónoma de WiFi, router y datos móviles."""

    # Configuración — adaptar a tu red
    ROUTER_IP = "192.168.1.1"
    ROUTER_USER = "admin"
    LATENCIA_ALERTA_MS = 100
    VELOCIDAD_MINIMA_MBPS = 10

    def __init__(self):
        self.estado_anterior = "ok"
        self.log_path = Path("logs/red_telefonia.json")

    # ── WiFi ──────────────────────────────────────────────
    def estado_wifi(self) -> dict:
        """Estado actual de la conexión WiFi."""
        resultado = ejecutar("networksetup -getairportnetwork en0")
        ssid = resultado.get("stdout", "").strip()
        ping = self._medir_latencia()
        return {
            "conectado": "You are not associated" not in ssid,
            "ssid": ssid,
            "latencia_ms": ping,
            "estado": "ok" if ping < self.LATENCIA_ALERTA_MS else "lento",
        }

    def listar_redes(self) -> list:
        """Lista redes WiFi disponibles."""
        resultado = ejecutar(
            "/System/Library/PrivateFrameworks/Apple80211.framework/"
            "Versions/Current/Resources/airport -s"
        )
        return resultado.get("stdout", "").strip().split("\n")

    def cambiar_red(self, ssid: str, password: str = "") -> dict:
        """Cambia a una red WiFi específica."""
        cmd = f"networksetup -setairportnetwork en0 '{ssid}' '{password}'"
        return ejecutar(cmd)

    def _medir_latencia(self, host: str = "8.8.8.8", count: int = 3) -> float:
        """Mide latencia en ms (devuelve 9999.0 si falla)."""
        resultado = ejecutar(f"ping -c {count} {host}")
        try:
            linea = next(line for line in resultado.get("stdout", "").split("\n") if "avg" in line)
            return float(linea.split("/")[4])
        except Exception:
            return 9999.0

    # ── Router Telefónica ──────────────────────────────────
    def estado_router(self) -> dict:
        """Health check del router."""
        try:
            r = requests.get(f"http://{self.ROUTER_IP}", timeout=5)
            return {"ok": True, "status": r.status_code, "ip": self.ROUTER_IP}
        except Exception as e:
            return {"ok": False, "error": str(e), "ip": self.ROUTER_IP}

    def dispositivos_conectados(self) -> list:
        """Lista dispositivos conectados al router via ARP."""
        resultado = ejecutar("arp -a | grep -v incomplete")
        lineas = resultado.get("stdout", "").strip().split("\n")
        return [linea.strip() for linea in lineas if linea]

    def reiniciar_router(self) -> dict:
        """Reinicia el router si no responde (requiere credenciales)."""
        logger.warning("Intento de reinicio de router")
        try:
            # Intento via API REST (Movistar/Telefónica Smart WiFi)
            r = requests.post(
                f"http://{self.ROUTER_IP}/reboot",
                auth=(self.ROUTER_USER, ""),
                timeout=10,
            )
            return {"ok": True, "status": r.status_code}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Datos móviles ──────────────────────────────────────
    def velocidad_internet(self) -> dict:
        """Mide velocidad de descarga aproximada (1MB en Mbps)."""
        try:
            url = "http://speedtest.tele2.net/1MB.zip"
            inicio = time.time()
            urllib.request.urlretrieve(url, "/tmp/speedtest_ura.tmp")  # noqa: S310
            duracion = time.time() - inicio
            mbps = round((1 * 8) / duracion, 2)  # 1 MB en Mbps
            return {
                "ok": True,
                "mbps": mbps,
                "estado": "ok" if mbps > self.VELOCIDAD_MINIMA_MBPS else "lento",
            }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    # ── Monitor autónomo ──────────────────────────────────
    def monitorear(self) -> dict:
        """Ciclo de monitoreo completo."""
        wifi = self.estado_wifi()
        router = self.estado_router()
        estado_actual = "ok"

        if not wifi["conectado"]:
            estado_actual = "sin_wifi"
            logger.critical("Sin conexión WiFi")
        elif wifi["latencia_ms"] > self.LATENCIA_ALERTA_MS:
            estado_actual = "lento"
            logger.warning(f"Latencia alta: {wifi['latencia_ms']}ms")
        elif not router["ok"]:
            estado_actual = "router_caido"
            logger.error("Router no responde")

        # Auto-acción si el estado empeoró
        if estado_actual != "ok" and self.estado_anterior == "ok":
            self._auto_accion(estado_actual)

        self.estado_anterior = estado_actual
        return {"wifi": wifi, "router": router, "estado": estado_actual}

    def _auto_accion(self, problema: str) -> None:
        """Acciones automáticas según el problema detectado."""
        if problema == "sin_wifi":
            logger.info("Intentando reconectar WiFi...")
            ejecutar("networksetup -setairportpower en0 off")
            time.sleep(2)
            ejecutar("networksetup -setairportpower en0 on")
        elif problema == "router_caido":
            logger.info("Router caído — registrando para notificación")
        elif problema == "lento":
            logger.warning("Conexión lenta — registrando métricas")

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteRedTelefonia."""
        texto.lower()
        return "Especialista en WiFi, router, Movistar y datos móviles. ¿Qué problema telefónico tienes?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteRedTelefonia."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteRedTelefonia."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteRedTelefonia."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteRedTelefonia.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            texto = args[0] if args else kwargs.get("texto", "")
            if not texto:
                return {"success": False, "response": "", "error": "No se proporcionó texto"}

            response = self.procesar(texto)
            return {"success": True, "response": response, "error": ""}
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}
