#!/usr/bin/env python3
"""
Messaging Callbacks - Paso 3A
─────────────────────────────
Callbacks para lectores de mensajería.
"""

import logging

logger = logging.getLogger(__name__)


def on_whatsapp_finished(window, chats):
    """Callback cuando WhatsApp termina de leer."""
    window.whatsapp_reader.on_finished(chats)


def on_whatsapp_error(window, error_msg):
    """Callback cuando hay error en WhatsApp."""
    window.whatsapp_reader.on_error(error_msg)


def on_email_finished(window, emails):
    """Callback cuando Email termina de leer."""
    window.email_reader.on_finished(emails)


def on_email_error(window, error_msg):
    """Callback cuando hay error en Email."""
    window.email_reader.on_error(error_msg)


def on_telegram_finished(window, messages):
    """Callback cuando Telegram termina de leer."""
    window.telegram_reader.on_finished(messages)


def on_telegram_error(window, error_msg):
    """Callback cuando hay error en Telegram."""
    window.telegram_reader.on_error(error_msg)


def on_instagram_finished(window, messages):
    """Callback cuando Instagram termina de leer."""
    window.instagram_reader.on_finished(messages)


def on_instagram_error(window, error_msg):
    """Callback cuando hay error en Instagram."""
    window.instagram_reader.on_error(error_msg)
