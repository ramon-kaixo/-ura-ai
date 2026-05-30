#!/usr/bin/env python3
"""Tests for core/stealth_fetcher.py — solo unit-level (sin red)."""

from __future__ import annotations


from core.stealth_fetcher import _extract_main_text


def test_extract_main_text_strips_scripts_and_styles():
    html = """
    <html><head><style>body{color:red}</style><script>alert(1)</script></head>
    <body>
      <nav>Menú nav</nav>
      <main>Contenido principal de la página</main>
      <footer>copyright</footer>
    </body></html>
    """
    text = _extract_main_text(html)
    assert "Contenido principal" in text
    assert "alert" not in text
    assert "Menú nav" not in text
    assert "copyright" not in text


def test_extract_main_text_falls_back_to_body_when_no_main():
    html = "<html><body><p>Hola mundo</p><p>Línea 2</p></body></html>"
    text = _extract_main_text(html)
    assert "Hola mundo" in text
    assert "Línea 2" in text


def test_extract_main_text_normalizes_whitespace():
    html = "<html><body><p>uno    dos\n\n  tres</p></body></html>"
    text = _extract_main_text(html)
    assert text == "uno dos tres"


def test_extract_main_text_empty_input_returns_empty():
    assert _extract_main_text("") == ""


def test_extract_main_text_prefers_article_over_body():
    html = """
    <html><body>
      <p>fuera del article</p>
      <article>Texto del artículo principal</article>
    </body></html>
    """
    text = _extract_main_text(html)
    assert "Texto del artículo principal" in text
    assert "fuera del article" not in text
