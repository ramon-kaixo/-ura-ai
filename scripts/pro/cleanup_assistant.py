#!/usr/bin/env python3
"""Limpieza automática de conversaciones antiguas.
Ejecutar diariamente: crontab -e → @daily python3 /path/to/cleanup.py
"""

import sys

sys.path.insert(0, "/home/ramon/URA/ura_ia_1972")
from motor.assistant.message_store import MessageStore

store = MessageStore()
deleted = store.cleanup_old(days=30)
print(f"Limpieza completada: {deleted} mensajes antiguos eliminados")
