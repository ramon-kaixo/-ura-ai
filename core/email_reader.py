#!/usr/bin/env python3
"""
core/email_reader.py - Lector de Correo Electrónico (Gmail/Outlook)
Lee correos NO leídos y permite responder bajo demanda
"""

import asyncio
import json
import logging
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config"
SESSION_PATH = Path(__file__).parent.parent / "data" / "email_session"

# Crear directorios
SESSION_PATH.mkdir(parents=True, exist_ok=True)


@dataclass
class EmailMessage:
    """Información de un correo"""

    id: str
    from_email: str
    from_name: str
    subject: str
    date: str
    snippet: str
    has_attachments: bool
    attachment_names: list[str]
    is_unread: bool


class EmailReader:
    """Lector de Correo Electrónico (Gmail/Outlook)"""

    def __init__(self, provider: str = "gmail"):
        self.provider = provider.lower()
        self.session_file = SESSION_PATH / f"{self.provider}_session.json"
        self.credentials_file = CONFIG_PATH / f"{self.provider}_credentials.json"
        self.token_file = CONFIG_PATH / f"{self.provider}_token.json"

    async def connect(self) -> bool:
        """
        Conectar al proveedor de correo con OAuth2

        Returns:
            True si conexión exitosa
        """
        try:
            logger.info(f"Conectando a {self.provider.upper()}...")

            if self.provider == "gmail":
                return await self._connect_gmail()
            elif self.provider == "outlook":
                return await self._connect_outlook()
            else:
                logger.error(f"Proveedor no soportado: {self.provider}")
                return False

        except Exception as e:
            logger.error(f"Error conectando a {self.provider}: {e}")
            return False

    async def _connect_gmail(self) -> bool:
        """Conectar a Gmail usando OAuth2"""
        try:
            import webbrowser

            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow

            # Scopes necesarios para Gmail
            SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
            ]

            # Verificar si existe token guardado
            if self.token_file.exists():
                with open(self.token_file) as f:
                    token_data = json.load(f)

                # Crear credenciales desde token guardado
                credentials = Credentials.from_authorized_user_info(token_data, SCOPES)

                if credentials.expired and credentials.refresh_token:
                    credentials.refresh(Request())
                    # Guardar token actualizado
                    self._save_gmail_token(credentials)

                logger.info("✅ Sesión de Gmail cargada")
                return True

            # Si no hay token, iniciar flujo OAuth
            if not self.credentials_file.exists():
                logger.error(f"❌ No existe {self.credentials_file}")
                return False

            logger.info("🔐 Iniciando flujo OAuth para Gmail...")
            logger.info(f"📍 Sesión se guardará en: {self.token_file}")

            flow = InstalledAppFlow.from_client_secrets_file(
                str(self.credentials_file), scopes=SCOPES
            )

            # Generar URL de autorización
            auth_url, _ = flow.authorization_url(
                access_type="offline", include_granted_scopes="true", prompt="consent"
            )

            print("\n" + "=" * 60)
            print("🔐 AUTENTICACIÓN GMAIL")
            print("=" * 60)
            print("🌐 Abriendo navegador para autorización...")
            print(f"📍 URL: {auth_url}")
            print("=" * 60)

            # Abrir navegador
            webbrowser.open(auth_url)

            print("\n📱 Autoriza la aplicación en el navegador...")
            print("👉 Pulsa ENTER aquí cuando termines...")
            input()

            # Intercambiar código por credenciales
            credentials = flow.credentials

            # Guardar token
            self._save_gmail_token(credentials)

            logger.info("✅ Sesión de Gmail iniciada correctamente")
            return True

        except ImportError as e:
            logger.error(f"❌ Faltan dependencias para Gmail: {e}")
            logger.info("💡 Instala: pip install google-api-python-client google-auth-oauthlib")
            return False
        except Exception as e:
            logger.error(f"❌ Error conectando a Gmail: {e}")
            return False

    def _save_gmail_token(self, credentials):
        """Guardar token de Gmail"""
        token_data = {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": credentials.scopes,
        }
        with open(self.token_file, "w") as f:
            json.dump(token_data, f, indent=2)

    async def _connect_outlook(self) -> bool:
        """Conectar a Outlook usando Microsoft Graph API"""
        logger.info("⚠️ Outlook aún no implementado - Usa Gmail por ahora")
        return False

    async def obtener_correos_no_leidos(self, max_emails: int = 20) -> list[EmailMessage]:
        """
        Obtener correos NO leídos

        Args:
            max_emails: Número máximo de correos a obtener

        Returns:
            Lista de correos no leídos
        """
        try:
            if self.provider == "gmail":
                return await self._get_gmail_unread(max_emails)
            elif self.provider == "outlook":
                return await self._get_outlook_unread(max_emails)
            else:
                return []

        except Exception as e:
            logger.error(f"Error obteniendo correos: {e}")
            return []

    async def _get_gmail_unread(self, max_emails: int) -> list[EmailMessage]:
        """Obtener correos no leídos de Gmail"""
        try:
            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Cargar credenciales
            if not self.token_file.exists():
                logger.error("❌ No existe token de Gmail")
                return []

            with open(self.token_file) as f:
                token_data = json.load(f)

            SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
            ]

            credentials = Credentials.from_authorized_user_info(token_data, SCOPES)

            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_gmail_token(credentials)

            # Crear servicio Gmail
            service = build("gmail", "v1", credentials=credentials)

            # Buscar correos no leídos
            results = (
                service.users()
                .messages()
                .list(userId="me", q="is:unread", maxResults=max_emails)
                .execute()
            )

            messages = results.get("messages", [])
            emails = []

            for msg in messages:
                try:
                    # Obtener detalles del mensaje
                    msg_detail = (
                        service.users()
                        .messages()
                        .get(
                            userId="me",
                            id=msg["id"],
                            format="metadata",
                            metadataHeaders=["From", "Subject", "Date"],
                        )
                        .execute()
                    )

                    # Extraer headers
                    headers = {
                        h["name"]: h["value"] for h in msg_detail["payload"].get("headers", [])
                    }

                    # Extraer adjuntos
                    has_attachments = "parts" in msg_detail["payload"]
                    attachment_names = []
                    if has_attachments:
                        for part in msg_detail["payload"].get("parts", []):
                            if "filename" in part and part["filename"]:
                                attachment_names.append(part["filename"])

                    # Crear objeto EmailMessage
                    email = EmailMessage(
                        id=msg["id"],
                        from_email=headers.get("From", ""),
                        from_name=headers.get("From", "").split("<")[0].strip(),
                        subject=headers.get("Subject", "(Sin asunto)"),
                        date=headers.get("Date", ""),
                        snippet=msg_detail.get("snippet", ""),
                        has_attachments=has_attachments,
                        attachment_names=attachment_names,
                        is_unread=True,
                    )

                    emails.append(email)

                except Exception as e:
                    logger.warning(f"Error procesando mensaje {msg['id']}: {e}")
                    continue

            logger.info(f"📊 {len(emails)} correos no leídos encontrados")
            return emails

        except ImportError as e:
            logger.error(f"❌ Faltan dependencias para Gmail: {e}")
            return []
        except Exception as e:
            logger.error(f"❌ Error obteniendo correos de Gmail: {e}")
            return []

    async def _get_outlook_unread(self, max_emails: int) -> list[EmailMessage]:
        """Obtener correos no leídos de Outlook"""
        logger.info("⚠️ Outlook aún no implementado - Usa Gmail por ahora")
        return []

    async def enviar_correo(self, to: str, subject: str, body: str) -> bool:
        """
        Enviar correo (solo bajo demanda del usuario)

        Args:
            to: Destinatario
            subject: Asunto
            body: Cuerpo del correo

        Returns:
            True si envío exitoso
        """
        try:
            if self.provider == "gmail":
                return await self._send_gmail(to, subject, body)
            elif self.provider == "outlook":
                return await self._send_outlook(to, subject, body)
            else:
                return False

        except Exception as e:
            logger.error(f"Error enviando correo: {e}")
            return False

    async def _send_gmail(self, to: str, subject: str, body: str) -> bool:
        """Enviar correo usando Gmail"""
        try:
            import base64
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            from google.auth.transport.requests import Request
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build

            # Cargar credenciales
            if not self.token_file.exists():
                logger.error("❌ No existe token de Gmail")
                return False

            with open(self.token_file) as f:
                token_data = json.load(f)

            SCOPES = [
                "https://www.googleapis.com/auth/gmail.readonly",
            ]

            credentials = Credentials.from_authorized_user_info(token_data, SCOPES)

            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                self._save_gmail_token(credentials)

            # Crear mensaje
            message = MIMEMultipart()
            message["to"] = to
            message["subject"] = subject
            message.attach(MIMEText(body, "plain"))

            # Codificar mensaje
            raw = base64.urlsafe_b64encode(message.as_bytes()).decode()

            # Crear servicio y enviar
            service = build("gmail", "v1", credentials=credentials)
            service.users().messages().send(userId="me", body={"raw": raw}).execute()

            logger.info(f"✅ Correo enviado a {to}")
            return True

        except Exception as e:
            logger.error(f"❌ Error enviando correo: {e}")
            return False

    async def _send_outlook(self, to: str, subject: str, body: str) -> bool:
        """Enviar correo usando Outlook"""
        logger.info("⚠️ Outlook aún no implementado - Usa Gmail por ahora")
        return False


async def obtener_correos_no_leidos(
    provider: str = "gmail", max_emails: int = 20
) -> list[EmailMessage]:
    """
    Función principal para obtener correos no leídos

    Args:
        provider: Proveedor de correo (gmail/outlook)
        max_emails: Número máximo de correos a obtener

    Returns:
        Lista de correos no leídos
    """
    reader = EmailReader(provider=provider)

    # Conectar
    if not await reader.connect():
        logger.error("❌ No se pudo conectar al proveedor de correo")
        return []

    # Obtener correos
    emails = await reader.obtener_correos_no_leidos(max_emails=max_emails)

    return emails


def mostrar_correos_en_consola(emails: list[EmailMessage]):
    """
    Mostrar correos en consola de URA

    Args:
        emails: Lista de correos a mostrar
    """
    if not emails:
        print("📭 No hay correos no leídos")
        return

    print("\n" + "=" * 60)
    print("📧 CORREOS NO LEÍDOS")
    print("=" * 60)

    for i, email in enumerate(emails, 1):
        print(f"\n📩 Correo {i}")
        print(f"   👤 De: {email.from_name} <{email.from_email}>")
        print(f"   📝 Asunto: {email.subject}")
        print(f"   ⏰ Fecha: {email.date}")
        if email.has_attachments:
            print(f"   📎 Adjuntos: {', '.join(email.attachment_names)}")
        print(f"   💬 Resumen: {email.snippet[:100]}...")

    print("\n" + "=" * 60)
    print(f"Total: {len(emails)} correos no leídos")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    # Prueba del lector de correo
    async def main():
        print("🔐 Iniciando lector de correo (Gmail)...")
        print("⚠️ Modo SOLO LECTURA por defecto")
        print("📤 Respuesta solo bajo demanda\n")

        emails = await obtener_correos_no_leidos(provider="gmail", max_emails=10)

        mostrar_correos_en_consola(emails)

    asyncio.run(main())
