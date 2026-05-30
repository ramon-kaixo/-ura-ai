#!/usr/bin/env python3
"""
Agente de Conectividad — autonomous multi-IP management.
Detects and switches between Cloudflare Tunnel, VPS, and ISP providers.
"""

import json
import logging
import threading
import time
from pathlib import Path

import requests

from core.ejecutor_seguro import ejecutar

logger = logging.getLogger(__name__)


class AgenteConectividad:
    """Gestion autonoma de IPs fijas, dinamicas y tunnels."""

    PROVEEDORES = [
        {
            "nombre": "cloudflare_tunnel",
            "tipo": "tunnel",
            "comando_check": "cloudflared tunnel list",
            "comando_start": "cloudflared tunnel run ura-tunnel",
            "prioridad": 1,
        },
        {
            "nombre": "vps_hetzner",
            "tipo": "vps",
            "host": "",
            "puerto": 22,
            "prioridad": 2,
        },
        {
            "nombre": "telefonica_dinamica",
            "tipo": "isp",
            "prioridad": 3,
        },
    ]

    def __init__(self):
        self.proveedor_activo = None
        self.ip_publica_actual = None
        self.historial = []
        self._lock = threading.Lock()

    def detectar_mejor_proveedor(self) -> dict:
        """Detecta y activa el mejor proveedor disponible."""
        for proveedor in sorted(self.PROVEEDORES, key=lambda x: x["prioridad"]):
            disponible = self._verificar_proveedor(proveedor)
            if disponible:
                if self.proveedor_activo != proveedor["nombre"]:
                    logger.info(f"Cambiando a proveedor: {proveedor['nombre']}")
                    self._activar_proveedor(proveedor)
                return {
                    "ok": True,
                    "proveedor": proveedor["nombre"],
                    "ip": self.ip_publica_actual,
                }
        return {"ok": False, "error": "Sin conectividad disponible"}

    def _verificar_proveedor(self, proveedor: dict) -> bool:
        """Verifica si un proveedor esta disponible."""
        try:
            if proveedor["tipo"] == "tunnel":
                r = ejecutar("cloudflared tunnel list 2>/dev/null")
                return r.get("ok", False)
            elif proveedor["tipo"] == "vps":
                host = proveedor.get("host", "")
                if not host:
                    return False
                r = ejecutar(f"ping -c 1 -W 2 {host}")
                return r.get("ok", False)
            elif proveedor["tipo"] == "isp":
                r = requests.get("https://api.ipify.org", timeout=5)
                return r.status_code == 200
        except Exception:
            return False
        return False

    def _activar_proveedor(self, proveedor: dict):
        """Activa un proveedor especifico."""
        with self._lock:
            self.proveedor_activo = proveedor["nombre"]
            self.ip_publica_actual = self._obtener_ip_publica()
            self.historial.append(
                {
                    "timestamp": time.time(),
                    "proveedor": proveedor["nombre"],
                    "ip": self.ip_publica_actual,
                }
            )
            self._guardar_estado()

    def _obtener_ip_publica(self) -> str:
        """Obtiene la IP publica actual."""
        try:
            r = requests.get("https://api.ipify.org?format=json", timeout=5)
            return r.json().get("ip", "desconocida")
        except Exception:
            return "desconocida"

    def ip_publica(self) -> dict:
        """Devuelve la IP publica actual con proveedor."""
        ip = self._obtener_ip_publica()
        return {
            "ip": ip,
            "proveedor": self.proveedor_activo,
            "fija": self.proveedor_activo in ["cloudflare_tunnel", "vps_hetzner"],
        }

    def instalar_cloudflare_tunnel(self) -> dict:
        """Instala y configura cloudflared si no esta instalado."""
        check = ejecutar("which cloudflared")
        if not check.get("ok"):
            logger.info("Instalando cloudflared via brew...")
            r = ejecutar("brew install cloudflared")
            if not r.get("ok"):
                return {"ok": False, "error": "No se pudo instalar cloudflared"}

        r = ejecutar("cloudflared tunnel create ura-tunnel")
        logger.info(f"Tunnel creado: {r.get('stdout', '')}")
        return {"ok": r.get("ok", False), "detalle": r.get("stdout", "")}

    def estado_tunnel(self) -> dict:
        """Estado del tunnel de Cloudflare."""
        r = ejecutar("cloudflared tunnel list 2>/dev/null")
        return {
            "ok": r.get("ok", False),
            "tunnels": r.get("stdout", "").strip().split("\n"),
        }

    def _guardar_estado(self):
        """Guarda el estado actual en JSON."""
        estado = {
            "proveedor_activo": self.proveedor_activo,
            "ip_publica": self.ip_publica_actual,
            "historial": self.historial[-50:],
        }
        Path("config/conectividad_estado.json").write_text(json.dumps(estado, indent=2))

    def monitorear(self) -> dict:
        """Ciclo de monitoreo — detecta y conmuta automaticamente."""
        return self.detectar_mejor_proveedor()

    def flujo_info(self) -> dict:
        """Muestra el flujo completo de informacion de red."""
        ip_info = self.ip_publica()
        tunnel = self.estado_tunnel()
        return {
            "ip_publica": ip_info["ip"],
            "ip_fija": ip_info["fija"],
            "proveedor_activo": ip_info["proveedor"],
            "tunnel_cloudflare": tunnel["ok"],
            "tunnels": tunnel["tunnels"],
            "historial_cambios": len(self.historial),
            "ultimo_cambio": self.historial[-1] if self.historial else None,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteConectividad."""
        texto.lower()
        return (
            "Puedo gestionar Cloudflare, túneles, IP y VPS. ¿Qué problema de conectividad tienes?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteConectividad."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteConectividad."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteConectividad."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteConectividad.

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
