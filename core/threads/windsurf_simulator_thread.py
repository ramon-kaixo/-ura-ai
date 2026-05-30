#!/usr/bin/env python3
"""
URA - Windsurf Thread (REAL)
Thread que envía prompts a Cascade AI de Windsurf vía AppleScript.
Si Windsurf no está disponible, usa Ollama como fallback (no simula).
"""

import logging

import requests
from PyQt5.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)


class WindsurfThread(QThread):
    """Thread real para interactuar con Windsurf Cascade."""

    response_ready = pyqtSignal(str)
    error_occurred = pyqtSignal(str)

    def __init__(self, prompt):
        super().__init__()
        self.prompt = prompt
        self._stop_requested = False

    def stop(self):
        self._stop_requested = True

    def run(self):
        # 1. Intentar con el conector real de Windsurf
        try:
            from connectors.windsurf_connector import WindsurfConnector

            wf = WindsurfConnector()
            if wf.detect_windsurf():
                response = wf.send_message(self.prompt, timeout=30)
                if response:
                    self.response_ready.emit(response)
                    return
        except Exception as e:
            logger.debug(f"Windsurf real no disponible: {e}")

        # 2. Fallback a Ollama local (real, no simulado)
        try:
            r = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3.2:3b",
                    "prompt": f"[URA → Windsurf fallback]\n{self.prompt}\n\nResponde en español, sé conciso:",
                    "stream": False,
                    "options": {"max_tokens": 200},
                },
                timeout=30,
            )
            response = r.json().get("response", "").strip()
            if response:
                self.response_ready.emit(f"[Windsurf vía Ollama] {response}")
                return
        except Exception as e:
            logger.debug(f"Ollama fallback no disponible: {e}")

        self.error_occurred.emit("Windsurf y Ollama no disponibles")
