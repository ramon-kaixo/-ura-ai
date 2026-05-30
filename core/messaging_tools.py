#!/usr/bin/env python3
"""
core/messaging_tools.py - Herramientas de mensajería para el asistente de IA
Permite que el asistente de IA pueda leer mensajes de WhatsApp, Gmail, Telegram e Instagram
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MessagingResult:
    """Resultado de una operación de mensajería"""

    success: bool
    messages: list[dict[str, Any]]
    error: str = ""
    summary: str = ""


class MessagingTools:
    """Herramientas de mensajería para el asistente de IA"""

    def __init__(self):
        pass

    async def read_whatsapp(self, max_chats: int = 20) -> MessagingResult:
        """
        Leer mensajes no leídos de WhatsApp

        Args:
            max_chats: Número máximo de chats a obtener

        Returns:
            MessagingResult con los mensajes encontrados
        """
        try:
            from core.whatsapp_reader import obtener_mensajes_whatsapp

            chats = await obtener_mensajes_whatsapp(headless=False, max_chats=max_chats)

            # Convertir a formato simple para el asistente
            messages = []
            for chat in chats:
                messages.append(
                    {
                        "chat_name": chat.get("name", "Desconocido"),
                        "unread_count": chat.get("unread_count", 0),
                        "last_message": chat.get("last_message", ""),
                        "timestamp": chat.get("timestamp", ""),
                    }
                )

            total_unread = sum(chat["unread_count"] for chat in chats)
            summary = f"Tienes {len(chats)} chats con {total_unread} mensajes no leídos en WhatsApp"

            return MessagingResult(success=True, messages=messages, summary=summary)

        except Exception as e:
            logger.error(f"Error leyendo WhatsApp: {e}")
            return MessagingResult(
                success=False,
                messages=[],
                error=str(e),
                summary="No se pudieron leer los mensajes de WhatsApp",
            )

    async def read_gmail(self, max_emails: int = 20) -> MessagingResult:
        """
        Leer correos no leídos de Gmail

        Args:
            max_emails: Número máximo de correos a obtener

        Returns:
            MessagingResult con los correos encontrados
        """
        try:
            from core.email_reader import obtener_correos_no_leidos

            emails = await obtener_correos_no_leidos(provider="gmail", max_emails=max_emails)

            # Convertir a formato simple para el asistente
            messages = []
            for email in emails:
                messages.append(
                    {
                        "from_name": email.from_name,
                        "from_email": email.from_email,
                        "subject": email.subject,
                        "date": email.date,
                        "has_attachments": email.has_attachments,
                        "attachment_names": email.attachment_names,
                        "snippet": email.snippet,
                    }
                )

            summary = f"Tienes {len(emails)} correos no leídos en Gmail"

            return MessagingResult(success=True, messages=messages, summary=summary)

        except Exception as e:
            logger.error(f"Error leyendo Gmail: {e}")
            return MessagingResult(
                success=False,
                messages=[],
                error=str(e),
                summary="No se pudieron leer los correos de Gmail",
            )

    async def read_telegram(self, max_chats: int = 20) -> MessagingResult:
        """
        Leer mensajes no leídos de Telegram

        Args:
            max_chats: Número máximo de chats a obtener

        Returns:
            MessagingResult con los mensajes encontrados
        """
        try:
            from core.telegram_reader import obtener_mensajes_telegram

            messages = await obtener_mensajes_telegram(max_chats=max_chats)

            # Convertir a formato simple para el asistente
            formatted_messages = []
            for msg in messages:
                formatted_messages.append(
                    {
                        "from_name": msg.from_name,
                        "chat_name": msg.chat_name,
                        "text": msg.text,
                        "date": msg.date,
                        "is_group": msg.is_group,
                    }
                )

            summary = f"Tienes {len(messages)} mensajes no leídos en Telegram"

            return MessagingResult(success=True, messages=formatted_messages, summary=summary)

        except Exception as e:
            logger.error(f"Error leyendo Telegram: {e}")
            return MessagingResult(
                success=False,
                messages=[],
                error=str(e),
                summary="No se pudieron leer los mensajes de Telegram",
            )

    async def read_instagram(self, max_threads: int = 20) -> MessagingResult:
        """
        Leer DMs no leídos de Instagram

        Args:
            max_threads: Número máximo de hilos a obtener

        Returns:
            MessagingResult con los DMs encontrados
        """
        try:
            from core.instagram_reader import obtener_dms_instagram

            messages = await obtener_dms_instagram(max_threads=max_threads)

            # Convertir a formato simple para el asistente
            formatted_messages = []
            for msg in messages:
                formatted_messages.append(
                    {
                        "from_username": msg.from_username,
                        "from_full_name": msg.from_full_name,
                        "text": msg.text,
                        "date": msg.date,
                        "has_media": msg.has_media,
                        "media_type": msg.media_type,
                    }
                )

            summary = f"Tienes {len(messages)} DMs no leídos en Instagram"

            return MessagingResult(success=True, messages=formatted_messages, summary=summary)

        except Exception as e:
            logger.error(f"Error leyendo Instagram: {e}")
            return MessagingResult(
                success=False,
                messages=[],
                error=str(e),
                summary="No se pudieron leer los DMs de Instagram",
            )

    async def send_gmail(self, to: str, subject: str, body: str) -> MessagingResult:
        """
        Enviar correo usando Gmail (solo bajo demanda del usuario)

        Args:
            to: Destinatario
            subject: Asunto
            body: Cuerpo del correo

        Returns:
            MessagingResult con el resultado
        """
        try:
            from core.email_reader import EmailReader

            reader = EmailReader()

            # Conectar
            if not await reader.connect():
                return MessagingResult(
                    success=False,
                    messages=[],
                    error="No se pudo conectar a Gmail",
                    summary="Error de conexión a Gmail",
                )

            # Enviar correo
            success = await reader.enviar_correo(to, subject, body)

            if success:
                return MessagingResult(success=True, messages=[], summary=f"Correo enviado a {to}")
            else:
                return MessagingResult(
                    success=False,
                    messages=[],
                    error="No se pudo enviar el correo",
                    summary="Error al enviar el correo",
                )

        except Exception as e:
            logger.error(f"Error enviando correo: {e}")
            return MessagingResult(
                success=False, messages=[], error=str(e), summary="No se pudo enviar el correo"
            )


# Instancia global de herramientas de mensajería
messaging_tools = MessagingTools()


# Funciones síncronas para el asistente de IA
def read_whatsapp_sync(max_chats: int = 20) -> dict[str, Any]:
    """Leer WhatsApp de forma síncrona (para el asistente de IA)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(messaging_tools.read_whatsapp(max_chats))
        loop.close()
        return {
            "success": result.success,
            "messages": result.messages,
            "error": result.error,
            "summary": result.summary,
        }
    finally:
        loop.close()


def read_gmail_sync(max_emails: int = 20) -> dict[str, Any]:
    """Leer Gmail de forma síncrona (para el asistente de IA)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(messaging_tools.read_gmail(max_emails))
        loop.close()
        return {
            "success": result.success,
            "messages": result.messages,
            "error": result.error,
            "summary": result.summary,
        }
    finally:
        loop.close()


def read_telegram_sync(max_chats: int = 20) -> dict[str, Any]:
    """Leer Telegram de forma síncrona (para el asistente de IA)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(messaging_tools.read_telegram(max_chats))
        loop.close()
        return {
            "success": result.success,
            "messages": result.messages,
            "error": result.error,
            "summary": result.summary,
        }
    finally:
        loop.close()


def read_instagram_sync(max_threads: int = 20) -> dict[str, Any]:
    """Leer Instagram de forma síncrona (para el asistente de IA)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(messaging_tools.read_instagram(max_threads))
        loop.close()
        return {
            "success": result.success,
            "messages": result.messages,
            "error": result.error,
            "summary": result.summary,
        }
    finally:
        loop.close()


def send_gmail_sync(to: str, subject: str, body: str) -> dict[str, Any]:
    """Enviar Gmail de forma síncrona (para el asistente de IA)"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        result = loop.run_until_complete(messaging_tools.send_gmail(to, subject, body))
        loop.close()
        return {
            "success": result.success,
            "messages": result.messages,
            "error": result.error,
            "summary": result.summary,
        }
    finally:
        loop.close()
