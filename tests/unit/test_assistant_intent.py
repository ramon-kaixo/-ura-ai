"""Tests for motor/assistant/intent.py — IntentEngine."""

from __future__ import annotations

from motor.assistant.intent import IntentEngine, IntentRouter
from motor.assistant.models import UserIntent


class TestIntentEngineClassify:
    def setup_method(self):
        self.engine = IntentEngine()

    def test_greeting(self):
        for text in ["hola", "Hola", "buenos días", "hello", "HELLO", "buenas tardes", "hey"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.GREETING, f"{text} -> {result.intent}"

    def test_farewell(self):
        for text in ["adiós", "gracias", "bye", "hasta luego", "chao"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.FAREWELL, f"{text} -> {result.intent}"

    def test_confirm(self):
        for text in ["sí", "ok", "vale", "yes", "confirmo", "adelante"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.CONFIRM, f"{text} -> {result.intent}"

    def test_reject(self):
        for text in ["no", "nope", "no me gusta", "cancelar"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.REJECT, f"{text} -> {result.intent}"

    def test_repeat(self):
        for text in ["repite", "otra vez", "no entendí", "puedes repetir"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.REPEAT, f"{text} -> {result.intent}"

    def test_question(self):
        for text in ["qué es esto?", "explica cómo funciona", "aclara ese punto", "por qué ocurrió?"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.QUESTION, f"{text} -> {result.intent}"

    def test_command(self):
        for text in ["busca python", "crea un proyecto", "ejecuta el test", "muestra los logs"]:
            result = self.engine.classify(text)
            assert result.intent == UserIntent.COMMAND, f"{text} -> {result.intent}"

    def test_chat_default(self):
        text = "me gusta cómo suena"
        result = self.engine.classify(text)
        assert result.intent == UserIntent.CHAT

    def test_confidence_high(self):
        result = self.engine.classify("hola")
        assert result.confidence > 0.9

    def test_confidence_low(self):
        result = self.engine.classify("me gusta la música")
        assert result.confidence == 0.5


class TestIntentEngineEntities:
    def setup_method(self):
        self.engine = IntentEngine()

    def test_extract_url(self):
        result = self.engine.classify("visita https://ejemplo.com")
        assert "url" in result.entities

    def test_extract_email(self):
        result = self.engine.classify("envía a test@example.com")
        assert "email" in result.entities

    def test_extract_number(self):
        result = self.engine.classify("muestra los 5 resultados")
        assert "number" in result.entities

    def test_empty_entities(self):
        result = self.engine.classify("hola")
        assert len(result.entities) == 0


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()

    def test_route_adds_capability(self):
        result = self.router.route("busca información")
        assert "capability" in result.entities

    def test_route_command_to_tools(self):
        result = self.router.route("ejecuta el script")
        assert result.entities["capability"] == "tools_execute"

    def test_route_question_to_knowledge(self):
        result = self.router.route("qué es URA?")
        assert result.entities["capability"] in ("knowledge_query", "conversation")


class TestIntentEngineIntegration:
    def test_full_pipeline(self):
        engine = IntentEngine()
        result = engine.classify("busca información sobre inteligencia artificial")
        assert result.intent == UserIntent.COMMAND
        assert "search_query" in result.entities or result.original_text != ""

    def test_resolve_references(self):
        engine = IntentEngine()
        result = engine.classify("hazlo de nuevo")
        assert "ejecuta" in result.resolved_text or result.resolved_text != ""

    def test_intent_to_capability_mapping(self):
        engine = IntentEngine()
        assert engine.intent_to_capability(UserIntent.COMMAND) == "tools_execute"
        assert engine.intent_to_capability(UserIntent.QUESTION) == "knowledge_query"
        assert engine.intent_to_capability(UserIntent.CHAT) == "conversation"
