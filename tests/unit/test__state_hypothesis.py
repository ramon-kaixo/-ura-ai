"""Tests property-based generados por plantilla (hypothesis)."""

from hypothesis import given, settings, assume
from hypothesis import strategies as st

from motor.core.llm._state import build_llm_state

