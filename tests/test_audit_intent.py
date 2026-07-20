"""Edge-case audit tests for motor/assistant/intent.py.

Targets: ReDoS, multiline false negatives, empty/whitespace edge cases,
reference resolution mutability, entity extraction blowup.
"""

from __future__ import annotations

import re
import time

import pytest

from motor.assistant.intent import IntentEngine, IntentRouter
from motor.assistant.models import UserIntent

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> IntentEngine:
    return IntentEngine()


# ---------------------------------------------------------------------------
# C1 — ReDoS / Regex Performance
# ---------------------------------------------------------------------------

class TestReDoS:
    """C1: Entity patterns can cause O(n²) behaviour on adversarial input.

    The search_query entity pattern: (?:busca|search)\\s*(?:sobre|de|acerca de)?
    \\s*['\"]?(.+?)['\"]?(?:\\s|$|\\.)

    The lazy (.+?) with two optional quotes and a trailing alternation forces
    the engine to expand one char at a time on long strings without spaces.
    """

    LARGE = 100_000

    def test_search_query_entity_regex_performance(self) -> None:
        engine = _make_engine()
        # Input with many 'a' chars forcing lazy expansion — should not hang
        long_input = "busca " + "a" * self.LARGE
        t0 = time.monotonic()
        result = engine.classify(long_input)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"ReDoS candidate took {elapsed:.2f}s"
        assert result.intent == UserIntent.COMMAND

    def test_question_pattern_all_input(self) -> None:
        """.*\\?$ matches ANY string ending with ? — test large."""
        engine = _make_engine()
        long_q = "a" * self.LARGE + "?"
        t0 = time.monotonic()
        result = engine.classify(long_q)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f".*\\?$ backtrack on {self.LARGE} chars took {elapsed:.2f}s"
        assert result.intent == UserIntent.QUESTION

    def test_url_entity_captures_unbounded(self) -> None:
        engine = _make_engine()
        long_url = "http://" + "a" * self.LARGE
        t0 = time.monotonic()
        result = engine.classify(long_url)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"URL entity took {elapsed:.2f}s"
        assert "url" in result.entities
        assert len(result.entities["url"]) > self.LARGE

    def test_email_entity_captures_unbounded(self) -> None:
        engine = _make_engine()
        user = "a" * self.LARGE
        t0 = time.monotonic()
        engine.classify(f"email {user}@example.com")
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"Email entity took {elapsed:.2f}s"

    def test_path_entity_regex_performance(self) -> None:
        engine = _make_engine()
        long_input = "ruta " + "a" * self.LARGE
        t0 = time.monotonic()
        engine.classify(long_input)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"Path entity took {elapsed:.2f}s"

    def test_repeat_redos_crafted_input(self) -> None:
        """Crafted to stress lazy+optional patterns simultaneously."""
        engine = _make_engine()
        evil = "busca " + "a" * 5_000 + "'" + "b" * 5_000
        t0 = time.monotonic()
        result = engine.classify(evil)
        elapsed = time.monotonic() - t0
        assert elapsed < 3.0, f"Crafted ReDoS took {elapsed:.2f}s"
        assert "search_query" in result.entities

    @pytest.mark.parametrize("pattern_src", [
        r"^(corrige|no\s*es\s*correcto|en\s*realidad|mejor\s*d[ií]|rectifica)",
        r"^(aclara|explica|qu[eé]\s*es|c[oó]mo\s*funciona|por\s*qu[eé]|cu[aá]ndo|d[oó]nde|qui[eé]n)",
    ])
    def test_dangling_start_anchor_patterns(self, pattern_src: str) -> None:
        """Patterns anchored only at start can match unexpectedly long strings."""
        pat = re.compile(pattern_src)
        long_text = "corrige" + "x" * 10_000
        t0 = time.monotonic()
        m = pat.search(long_text)
        elapsed = time.monotonic() - t0
        assert elapsed < 1.0, f"Pattern took {elapsed:.2f}s on 10K chars"
        assert m is not None


# ---------------------------------------------------------------------------
# C2 — Multiline / Newline Edge Cases
# ---------------------------------------------------------------------------

class TestMultiline:
    """C2: .*\\?$ does NOT match across newlines (false negative)."""

    def test_multiline_question_false_negative(self) -> None:
        engine = _make_engine()
        text = "I was thinking about this\ncan you explain it?"
        result = engine.classify(text)
        # This SHOULD be QUESTION but the .*\\?$ won't match because
        # . doesn't cross \n by default
        assert result.intent == UserIntent.QUESTION, (
            f"Multiline question classified as {result.intent} (false negative)"
        )

    def test_multiline_command(self) -> None:
        engine = _make_engine()
        text = "first line\nbusca python"
        result = engine.classify(text)
        # BUSCA pattern is anchored at start: ^(busca|...)
        # "first line\nbusca python" does NOT start with busca
        assert result.intent == UserIntent.COMMAND, (
            f"Multiline command classified as {result.intent}"
        )

    def test_greeting_with_newline_prefix(self) -> None:
        engine = _make_engine()
        text = "\n\n\nhola"
        result = engine.classify(text)
        # After strip + lower: "\n\n\nhola" -> "hola"
        assert result.intent == UserIntent.GREETING, f"Expected GREETING got {result.intent}"

    def test_newline_suffix_question(self) -> None:
        engine = _make_engine()
        text = "qué es?\n"
        result = engine.classify(text)
        # After strip: "qué es?" which should be QUESTION
        assert result.intent == UserIntent.QUESTION, f"Expected QUESTION got {result.intent}"


# ---------------------------------------------------------------------------
# C3 — Empty / Whitespace / Special Input
# ---------------------------------------------------------------------------

class TestEmptyAndWhitespace:
    def test_empty_string(self) -> None:
        engine = _make_engine()
        result = engine.classify("")
        assert result.intent == UserIntent.UNKNOWN
        assert result.confidence == 0.0

    def test_whitespace_only(self) -> None:
        engine = _make_engine()
        result = engine.classify("   \t\n  ")
        assert result.intent == UserIntent.UNKNOWN
        assert result.confidence == 0.0

    def test_only_punctuation(self) -> None:
        engine = _make_engine()
        result = engine.classify("!@#$%^&*()")
        assert result.intent != UserIntent.UNKNOWN

    def test_null_byte_in_text(self) -> None:
        engine = _make_engine()
        result = engine.classify("hola\x00world")
        assert result.intent == UserIntent.GREETING

    def test_unicode_accents_preserved(self) -> None:
        engine = _make_engine()
        result = engine.classify("qué es una API?")
        assert result.intent == UserIntent.QUESTION
        assert "é" in result.original_text

    def test_mixed_case_preserved_in_original(self) -> None:
        engine = _make_engine()
        result = engine.classify("BUSCA Python 3.12")
        assert result.intent == UserIntent.COMMAND
        assert result.original_text == "BUSCA Python 3.12"

    def test_very_long_input_classify(self) -> None:
        engine = _make_engine()
        text = "hola " + "amigo " * 10_000
        t0 = time.monotonic()
        result = engine.classify(text)
        elapsed = time.monotonic() - t0
        assert elapsed < 2.0, f"10K words took {elapsed:.2f}s"
        assert result.intent == UserIntent.GREETING


# ---------------------------------------------------------------------------
# C4 — False Positives / Negatives in Classification
# ---------------------------------------------------------------------------

class TestClassificationBoundaries:
    def test_question_mark_sentence_not_question(self) -> None:
        """.*\\?$ is overly broad — any sentence ending with ? is QUESTION."""
        engine = _make_engine()
        result = engine.classify("Esto es una afirmación?")
        assert result.intent == UserIntent.QUESTION, (
            f"Statement ending with ? classified as {result.intent} (overbroad)"
        )

    def test_greeting_with_question_mark(self) -> None:
        """'hola?' should be GREETING (higher confidence beats QUESTION)."""
        engine = _make_engine()
        result = engine.classify("hola?")
        # GREETING has 0.95 confidence; QUESTION has 0.8
        assert result.intent == UserIntent.GREETING, f"Expected GREETING got {result.intent}"

    def test_question_starts_with_command_word(self) -> None:
        engine = _make_engine()
        result = engine.classify("explica qué es una API")
        # "explica" matches both COMMAND (0.85) and QUESTION (0.8 via first pattern)
        # The first pattern checked is GREETING (no match), FAREWELL (no match),
        # CONFIRM (no), REJECT (no), REPEAT (no), CORRECT (no match),
        # then QUESTION: ^(aclara|explica|...) matches "explica" with conf 0.8
        # best_confidence becomes 0.8, best_intent becomes QUESTION
        # then COMMAND: ^(busca|crea|haz|ejecuta|muestra|...)
        # "explica" does NOT match any of these.
        # Wait, "explica" is not in the COMMAND pattern list.
        assert result.intent == UserIntent.QUESTION, f"Expected QUESTION got {result.intent}"

    def test_chat_fallback(self) -> None:
        engine = _make_engine()
        result = engine.classify("me gusta la música")
        assert result.intent == UserIntent.CHAT
        assert result.confidence == 0.5

    def test_command_matches_target_extraction(self) -> None:
        engine = _make_engine()
        action, target = engine.extract_action_and_target("busca información sobre python")
        assert action == "busca"
        assert "información sobre python" in target


# ---------------------------------------------------------------------------
# C5 — Reference Resolution Edge Cases
# ---------------------------------------------------------------------------

class TestReferenceResolution:
    def test_resolve_references_does_not_mutate_original(self) -> None:
        engine = _make_engine()
        original = "HAZLO DE NUEVO"
        result = engine.classify(original)
        # The original_text should not be lowercased
        assert result.original_text == "HAZLO DE NUEVO"

    def test_resolve_references_sequential_application(self) -> None:
        engine = _make_engine()
        result = engine.classify("hazlo como antes")
        # "hazlo" -> "ejecuta", "como antes" -> ""
        assert "ejecuta" in result.resolved_text

    def test_resolve_eso_replaces_with_empty(self) -> None:
        engine = _make_engine()
        result = engine.classify("haz eso")
        # "eso" -> "", "haz" is not in any command list... wait "haz" IS
        # in the COMMAND pattern: ^(busca|crea|haz|...)
        # But after resolve: "haz eso" -> lower -> "haz " (eso removed)
        # Then classified as COMMAND
        assert result.intent == UserIntent.COMMAND

    def test_resolve_references_no_match_preserves_text(self) -> None:
        engine = _make_engine()
        result = engine.classify("este texto no tiene referencias")
        assert result.resolved_text == "este texto no tiene referencias"


# ---------------------------------------------------------------------------
# C6 — Multiple Entities Extraction
# ---------------------------------------------------------------------------

class TestEntityExtraction:
    def test_multiple_entities_same_input(self) -> None:
        engine = _make_engine()
        result = engine.classify(
            "busca información sobre python envía a test@example.com "
            "visita https://example.com usa 42 veces"
        )
        assert "search_query" in result.entities or "email" in result.entities
        # Only first match per entity type is captured

    def test_entity_without_capture_group_fallback(self) -> None:
        """_extract_entities catches IndexError for missing groups."""
        engine = _make_engine()
        result = engine.classify("español")
        assert "language" in result.entities

    def test_date_entity_edge_formats(self) -> None:
        engine = _make_engine()
        for date_str in ["01/01/24", "31-12-2023", "1/1/2024"]:
            result = engine.classify(f"fecha {date_str}")
            assert "date" in result.entities, f"Date '{date_str}' not extracted"
            assert result.entities["date"] == date_str


# ---------------------------------------------------------------------------
# C7 — IntentRouter edge cases
# ---------------------------------------------------------------------------

class TestIntentRouterEdgeCases:
    def test_router_unknown_maps_to_conversation(self) -> None:
        router = IntentRouter()
        result = router.route("este es un texto aleatorio sin patrón")
        assert result.entities["capability"] == "conversation"

    def test_router_preserves_all_entities(self) -> None:
        router = IntentRouter()
        result = router.route("busca python en https://python.org envía a user@test.com")
        assert "capability" in result.entities
        assert result.entities["capability"] == "tools_execute"
