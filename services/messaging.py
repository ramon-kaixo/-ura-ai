#!/usr/bin/env python3
"""
Messaging Readers — extraídos de main_final.py (FASE 1)
WhatsApp, Email, Telegram, Instagram — lectura de mensajería.
Migrados a thread_pool global.
"""

import asyncio

from PyQt5.QtCore import QObject, pyqtSignal
from PyQt5.QtWidgets import QMessageBox


class PoolTask(QObject):
    """Wrapper que ejecuta una función en el thread_pool y emite señales Qt."""

    finished = pyqtSignal(object)
    error = pyqtSignal(str)

    def __init__(self, parent, func):
        super().__init__()
        self.parent = parent
        self.func = func

    def start(self):
        future = self.parent.thread_pool.submit(self._run)
        future.add_done_callback(self._on_done)

    def _run(self):
        return self.func()

    def _on_done(self, future):
        try:
            result = future.result()
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))


def read_whatsapp(parent):
    """Leer mensajes de WhatsApp (Solo Lectura). parent = URAMainWindowFinal."""
    try:
        from core.whatsapp_reader import obtener_mensajes_whatsapp

        def task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            chats = loop.run_until_complete(
                asyncio.wait_for(
                    obtener_mensajes_whatsapp(headless=False, max_chats=20),
                    timeout=300.0,
                )
            )
            loop.close()
            return chats

        QMessageBox.information(
            parent,
            "WhatsApp - Solo Lectura",
            "Buscando mensajes no leídos...\n\n"
            "Esto abrirá un navegador para conectar a WhatsApp Web.\n"
            "Si es la primera vez, necesitarás escanear el código QR.\n"
            "El sistema SOLO LEERÁ mensajes, no enviará nada.",
        )

        task_wrapper = PoolTask(parent, task)
        task_wrapper.finished.connect(parent.on_whatsapp_finished)
        task_wrapper.error.connect(parent.on_whatsapp_error)
        task_wrapper.start()

    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Error iniciando WhatsApp: {str(e)}")


def read_email(parent):
    """Leer correos no leídos (Gmail/Outlook)."""
    try:
        from core.email_reader import obtener_correos_no_leidos

        def task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            emails = loop.run_until_complete(
                asyncio.wait_for(
                    obtener_correos_no_leidos(provider="gmail", max_emails=20),
                    timeout=300.0,
                )
            )
            loop.close()
            return emails

        QMessageBox.information(
            parent,
            "Correo - Solo Lectura",
            "Buscando correos no leídos...\n\n"
            "Esto abrirá un navegador para conectar a Gmail.\n"
            "Si es la primera vez, necesitarás autorizar la aplicación.\n"
            "El sistema SOLO LEERÁ correos, no enviará nada automáticamente.",
        )

        task_wrapper = PoolTask(parent, task)
        task_wrapper.finished.connect(parent.on_email_finished)
        task_wrapper.error.connect(parent.on_email_error)
        task_wrapper.start()

    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Error iniciando correo: {str(e)}")


def read_telegram(parent):
    """Leer mensajes de Telegram (Solo Lectura)."""
    try:
        from core.telegram_reader import obtener_mensajes_telegram

        def task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            messages = loop.run_until_complete(
                asyncio.wait_for(obtener_mensajes_telegram(max_chats=20), timeout=300.0)
            )
            loop.close()
            return messages

        QMessageBox.information(
            parent,
            "Telegram - Solo Lectura",
            "Buscando mensajes no leídos...\n\n"
            "Si es la primera vez, necesitarás configurar config/telegram_config.json.\n"
            "El archivo debe contener: api_id, api_hash y phone.\n"
            "El sistema SOLO LEERÁ mensajes, no responderá nada.",
        )

        task_wrapper = PoolTask(parent, task)
        task_wrapper.finished.connect(parent.on_telegram_finished)
        task_wrapper.error.connect(parent.on_telegram_error)
        task_wrapper.start()

    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Error iniciando Telegram: {str(e)}")


def read_instagram(parent):
    """Leer mensajes directos de Instagram (Solo Lectura)."""
    try:
        from core.instagram_reader import obtener_dms_instagram

        def task():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            messages = loop.run_until_complete(
                asyncio.wait_for(obtener_dms_instagram(max_threads=20), timeout=300.0)
            )
            loop.close()
            return messages

        QMessageBox.information(
            parent,
            "Instagram - Solo Lectura",
            "Buscando DMs no leídos...\n\n"
            "Si es la primera vez, necesitarás configurar config/instagram_config.json.\n"
            "El archivo debe contener: username y password.\n"
            "El sistema SOLO LEERÁ DMs, no publicará ni enviará nada.",
        )

        task_wrapper = PoolTask(parent, task)
        task_wrapper.finished.connect(parent.on_instagram_finished)
        task_wrapper.error.connect(parent.on_instagram_error)
        task_wrapper.start()

    except Exception as e:
        QMessageBox.warning(parent, "Error", f"Error iniciando Instagram: {str(e)}")
