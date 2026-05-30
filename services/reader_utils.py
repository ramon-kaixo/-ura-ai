#!/usr/bin/env python3
"""
Reader Utils - Paso 3A
───────────────────────
Utilidades para lectores de mensajería.
"""

import logging

logger = logging.getLogger(__name__)


def read_whatsapp_messages(window):
    """Iniciar lectura de mensajes de WhatsApp."""
    window.whatsapp_reader.start()


def read_email_messages(window):
    """Iniciar lectura de emails."""
    window.email_reader.start()


def read_telegram_messages(window):
    """Iniciar lectura de mensajes de Telegram."""
    window.telegram_reader.start()


def read_instagram_messages(window):
    """Iniciar lectura de mensajes de Instagram."""
    window.instagram_reader.start()
