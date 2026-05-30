#!/usr/bin/env python3
"""
Fallback classes — cuando los módulos reales no se pueden importar.
"""


class MockOllamaConnector:
    def __init__(self):
        self.is_connected = False

    def test_connection(self, test_model=True):
        return False

    def generate(self, prompt, model=None, options=None):
        raise ConnectionError("Ollama no disponible")

    def get_models(self):
        return []

    def generate_stream(
        self, prompt, model=None, chunk_callback=None, options=None, use_system_prompt=False
    ):
        raise ConnectionError("Ollama no disponible")


class FallbackWorkflow:
    def __init__(self):
        pass

    def process(self, message):
        return f"Respuesta de URA: {message}"

    def get_models(self):
        return ["qwen2.5:3b-instruct"]

    def set_model(self, model):
        return True
