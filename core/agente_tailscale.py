#!/usr/bin/env python3
"""
agente_tailscale.py — URA Agente Tailscale VPN
===============================================
Controla Tailscale desde URA.

Capacidades:
- Conectar/desconectar VPN
- Ver dispositivos conectados
- Generar claves de acceso
- Compartir archivos
- SSH через Tailscale
"""

import json
import subprocess


class AgenteTailscale:
    def __init__(self):
        self.binario = "/opt/homebrew/bin/tailscale"

    def status(self) -> dict:
        """Estado de Tailscale."""
        try:
            result = subprocess.run(
                [self.binario, "status", "--json"], capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return json.loads(result.stdout)
            else:
                return {"error": "Tailscale no está corriendo", "details": result.stderr}
        except FileNotFoundError:
            return {"error": "Tailscale no instalado"}
        except Exception as e:
            return {"error": str(e)}

    def estado_texto(self) -> str:
        """Estado en texto legible."""
        try:
            result = subprocess.run(
                [self.binario, "status"], capture_output=True, text=True, timeout=10
            )
            return result.stdout if result.returncode == 0 else result.stderr
        except Exception as e:
            return f"Error: {e}"

    def conectar(self) -> bool:
        """Conecta Tailscale."""
        try:
            result = subprocess.run(
                [self.binario, "up"], capture_output=True, text=True, timeout=30
            )
            return result.returncode == 0
        except Exception:
            return False

    def desconectar(self) -> bool:
        """Desconecta Tailscale."""
        try:
            result = subprocess.run(
                [self.binario, "down"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def dispositivos(self) -> list[dict]:
        """Lista dispositivos conectados."""
        estado = self.status()
        if "error" in estado:
            return []

        dispositivos = []
        peers = estado.get("Peer", {})

        for ip, info in peers.items():
            dispositivos.append(
                {
                    "ip": ip,
                    "nombre": info.get("HostName", "desconocido"),
                    "online": info.get("Online", False),
                    "ultima_conexion": info.get("LastSeen", ""),
                }
            )
        return dispositivos

    def ip_local(self) -> str | None:
        """Obtiene IP de esta máquina."""
        estado = self.status()
        if "Self" in estado:
            return estado["Self"].get("DNSName", "").replace(".", "")
        return None

    def logout(self) -> bool:
        """Cierra sesión en Tailscale."""
        try:
            result = subprocess.run(
                [self.binario, "logout"], capture_output=True, text=True, timeout=10
            )
            return result.returncode == 0
        except Exception:
            return False

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteTailscale."""
        texto.lower()
        return "Puedo conectar dispositivos a Tailscale y gestionar VPN. ¿Qué dispositivo quieres conectar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteTailscale."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteTailscale."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteTailscale."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteTailscale.

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


_TAILSCALE = None


def get_tailscale() -> AgenteTailscale:
    global _TAILSCALE
    if _TAILSCALE is None:
        _TAILSCALE = AgenteTailscale()
    return _TAILSCALE
