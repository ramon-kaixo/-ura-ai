#!/usr/bin/env python3
"""
core/auth_google.py - Autenticación OAuth para Google Drive
Inicia el flujo OAuth y guarda token.json encriptado
"""

import base64
import contextlib
import json
import logging
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from google_auth_oauthlib.flow import InstalledAppFlow

logger = logging.getLogger(__name__)

# Rutas
CREDENTIALS_PATH = Path(__file__).parent.parent / "config" / "credentials.json"
TOKEN_PATH = Path(__file__).parent.parent / "config" / "token.json"

# Scopes necesarios para Google Drive
SCOPES = ["https://www.googleapis.com/auth/drive"]


def encrypt_token(token_data: dict) -> str:
    """Encriptar datos del token usando base64"""
    json_str = json.dumps(token_data)
    encrypted = base64.b64encode(json_str.encode()).decode()
    return encrypted


def decrypt_token(encrypted_str: str) -> dict:
    """Desencriptar datos del token"""
    decoded = base64.b64decode(encrypted_str.encode()).decode()
    return json.loads(decoded)


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handler para capturar el callback de OAuth"""

    def do_GET(self):
        """Procesar solicitud GET del callback OAuth"""
        try:
            # Parsear la URL para obtener el código de autorización
            parsed_url = urlparse(self.path)
            query_params = parse_qs(parsed_url.query)

            if "code" in query_params:
                auth_code = query_params["code"][0]

                # Guardar el código de autorización
                self.server.auth_code = auth_code

                # Enviar respuesta HTML al navegador
                self.send_response(200)
                self.send_header("Content-type", "text/html")
                self.end_headers()

                html = """
                <html>
                <head><title>Authentication Successful</title></head>
                <body>
                    <h1>Authentication Successful</h1>
                    <p>You can close this window and return to the terminal.</p>
                </body>
                </html>
                """
                self.wfile.write(html.encode("utf-8"))

                logger.info("Código de autorización recibido")

                # Detener el servidor después de recibir el código
                self.server.shutdown_requested = True
            else:
                self.send_response(400)
                self.send_header("Content-type", "text/html")
                self.end_headers()
                self.wfile.write(b"<h1>Error: Authorization code not received</h1>")

        except Exception as e:
            logger.error(f"Error procesando callback: {e}")
            self.send_response(500)
            self.end_headers()


def start_oauth_flow():
    """Iniciar flujo OAuth para Google Drive"""

    # Verificar que credentials.json existe
    if not CREDENTIALS_PATH.exists():
        logger.error(f"credentials.json no encontrado en {CREDENTIALS_PATH}")
        print(f"❌ Error: credentials.json no encontrado en {CREDENTIALS_PATH}")
        return False

    try:
        print("🔐 Iniciando flujo OAuth para Google Drive...")
        print(f"📁 Cargando credenciales de: {CREDENTIALS_PATH}")

        # Crear el flujo OAuth
        flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), scopes=SCOPES)

        # Configurar el flujo para usar el servidor local en puerto 8080
        flow.redirect_uri = "http://localhost:8080"

        # Generar URL de autorización
        auth_url, _ = flow.authorization_url(
            access_type="offline", include_granted_scopes="true", prompt="consent"
        )

        print("\n🌐 Abriendo navegador para autorización...")
        print(f"📍 URL de autorización: {auth_url}")
        print(
            "\n💡 Si el navegador no se abre automáticamente, copia y pega esta URL en tu navegador.\n"
        )

        # Abrir navegador automáticamente
        webbrowser.open(auth_url)

        # Iniciar servidor HTTP local para capturar el callback
        server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
        server.auth_code = None
        server.shutdown_requested = False

        print("⏳ Esperando autorización en http://localhost:8080...")
        print("   (Presiona Ctrl+C para cancelar)\n")

        # Esperar el callback (timeout de 5 minutos)
        server.timeout = 300
        server.handle_request()

        if hasattr(server, "auth_code") and server.auth_code:
            print("✅ Código de autorización recibido")

            # Intercambiar código por token
            flow.fetch_token(code=server.auth_code)

            # Obtener credenciales
            credentials = flow.credentials

            # Guardar credenciales encriptadas
            token_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "scopes": credentials.scopes,
            }

            # Encriptar y guardar
            encrypted_token = encrypt_token(token_data)
            with open(TOKEN_PATH, "w") as f:
                json.dump({"encrypted": True, "data": encrypted_token}, f, indent=2)

            print(f"\n✅ Token guardado exitosamente en: {TOKEN_PATH}")
            print("🎉 Autenticación completada. El sistema de backup a Google Drive está listo.\n")

            return True
        else:
            print("❌ Error: No se recibió código de autorización")
            return False

    except Exception as e:
        logger.error(f"Error en flujo OAuth: {e}")
        print(f"❌ Error en flujo OAuth: {e}")
        return False
    finally:
        with contextlib.suppress(BaseException):
            server.server_close()


if __name__ == "__main__":
    start_oauth_flow()
