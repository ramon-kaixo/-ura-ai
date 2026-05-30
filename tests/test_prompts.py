"""Tests para prompts versionados."""

from pathlib import Path

BASE = Path(__file__).parent.parent / "config" / "prompts"
PROMPTS = ["sistema.txt", "openclaw.txt", "clasificador.txt"]


def test_prompts_exist():
    for p in PROMPTS:
        assert (BASE / p).exists(), f"Falta: {p}"


def test_prompts_not_empty():
    for p in PROMPTS:
        content = (BASE / p).read_text()
        assert len(content.strip()) > 10, f"Vacio o muy corto: {p}"


def test_prompts_have_utf8():
    for p in PROMPTS:
        content = (BASE / p).read_bytes()
        content.decode("utf-8")
