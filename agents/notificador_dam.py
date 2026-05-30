#!/usr/bin/env python3
"""
Sistema de notificaciones reales para DAM
Usa Pushover + WhatsApp (Twilio) como respaldo
"""

import json
import os
import socket
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
CONFIG_PATH = BASE_DIR / "config" / "dam_config.json"

PUSHOVER_USER_KEY = os.getenv("PUSHOVER_USER_KEY", "")
PUSHOVER_APP_TOKEN = os.getenv("PUSHOVER_APP_TOKEN", "")

TWILIO_ACCOUNT_SID = None  # Poner aquí cuando lo tengas
TWILIO_AUTH_TOKEN = None
TWILIO_WHATSAPP_FROM = None


class NotificadorDAM:
    """Sistema de notificaciones via Pushover + WhatsApp"""

    def __init__(self):
        self.config = self._cargar_config()
        self.telefono_movil = "+34661890713"  # Tu número

    def _cargar_config(self):
        if CONFIG_PATH.exists():
            return json.loads(CONFIG_PATH.read_text())
        return {"pushover_config": {"enabled": False}}

    def _enviar_whatsapp(self, mensaje: str) -> dict:
        """Envía WhatsApp via Twilio como respaldo"""

        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN:
            return {"success": False, "error": "Twilio no configurado"}

        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"

            datos = {
                "From": TWILIO_WHATSAPP_FROM,
                "To": f"whatsapp:{self.telefono_movil}",
                "Body": mensaje,
            }

            respuesta = requests.post(
                url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN), data=datos, timeout=15
            )

            if respuesta.status_code in (200, 201):
                return {"success": True, "sid": respuesta.json().get("sid")}
            else:
                return {"success": False, "error": respuesta.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _enviar_pushover(
        self,
        titulo: str,
        mensaje: str,
        prioridad: int = 0,
        token: str = None,
        tiene_botones: bool = False,
    ) -> dict:
        """Envía notificación Pushover con botones"""

        datos = {
            "token": PUSHOVER_APP_TOKEN,
            "user": PUSHOVER_USER_KEY,
            "title": titulo,
            "message": mensaje,
            "priority": prioridad,
            "retry": 30 if prioridad == 2 else 0,
            "expire": 3600 if prioridad == 2 else 0,
            "sound": "siren" if prioridad == 2 else "bike",
        }

        if tiene_botones and token:
            datos["html"] = 1
            datos["message"] = (
                f"{mensaje}<br><br><a href='shortcuts://run-shortcut?name=Validar-URA&input=APROBAR&token={token}'>✅ APROBAR</a> | <a href='shortcuts://run-shortcut?name=Validar-URA&input=DENEGAR&token={token}'>❌ DENEGAR</a>"
            )

        try:
            respuesta = requests.post(
                "https://api.pushover.net/1/messages.json", data=datos, timeout=10
            )

            if respuesta.status_code == 200:
                return {"success": True, "id": respuesta.json().get("request")}
            else:
                return {"success": False, "error": respuesta.text}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _obtener_url_validacion(self, token: str) -> str:
        hostname = socket.gethostname()
        return f"http://{hostname}.local:8765/validar?token={token}"

    def enviar_validacion_movil(
        self, token: str, accion: str, nivel: str, descripcion: str
    ) -> dict:
        """Envía notificación al móvil (Pushover + WhatsApp backup)"""

        prioridad = 2 if nivel == "OMEGA" else 0
        titulo = f"🔐 URA: {nivel} - {accion}"
        url_validacion = self._obtener_url_validacion(token)

        mensaje = f"""
Acción: {accion}
Descripción: {descripcion}

⏰ {datetime.now().strftime("%H:%M:%S")}

👉 Abre para validar: {url_validacion}

{"⚠️ ACCIÓN CRÍTICA" if nivel == "OMEGA" else "✅ Acción normal"}"""

        push_result = self._enviar_pushover(titulo, mensaje.strip(), prioridad)

        if push_result["success"]:
            push_result["method"] = "pushover"
            return push_result

        whatsapp_msg = f"🔐 URA VALIDACIÓN\n\n{nivel}: {accion}\n{descripcion}\nToken: {token}"
        wa_result = self._enviar_whatsapp(whatsapp_msg)

        if wa_result["success"]:
            wa_result["method"] = "whatsapp"
            return wa_result

        return {
            "success": False,
            "error": "Ambos métodos fallaron",
            "pushover": push_result.get("error"),
            "whatsapp": wa_result.get("error"),
        }

    def enviar_alerta_critica(self, titulo: str, mensaje: str):
        """Envía alerta crítica inmediata al móvil"""

        push_result = self._enviar_pushover(f"🚨 {titulo}", mensaje, 2)

        if push_result["success"]:
            return True

        return self._enviar_whatsapp(f"🚨 URA ALERTA\n\n{titulo}\n{mensaje}")["success"]

    def test_sistema(self) -> dict:
        """Prueba ambos sistemas de notificación"""

        print("\n📱 Prueba Pushover...")
        push = self._enviar_pushover("🧪 Test URA", "Prueba de conexión Pushover", 0)

        print("📱 Prueba WhatsApp (respaldo)...")
        wa = self._enviar_whatsapp("🧪 URA: Prueba WhatsApp")

        return {"pushover": push, "whatsapp": wa}


# Instancia global
_NOTIFICADOR = None


def get_notificador() -> NotificadorDAM:
    global _NOTIFICADOR
    if _NOTIFICADOR is None:
        _NOTIFICADOR = NotificadorDAM()
    return _NOTIFICADOR


if __name__ == "__main__":
    notif = get_notificador()

    print("=" * 70)
    print("📱 SISTEMA DE NOTIFICACIONES (PUSHOVER + WHATSAPP)")
    print("=" * 70)

    resultado = notif.test_sistema()

    print("\n📊 Resultados:")
    print(f"   Pushover: {'✅ OK' if resultado['pushover']['success'] else '❌ FALLO'}")
    print(f"   WhatsApp: {'✅ OK' if resultado['whatsapp']['success'] else '❌ FALLO'}")

    if not resultado["pushover"]["success"]:
        print(f"\n   Error Pushover: {resultado['pushover'].get('error')}")
