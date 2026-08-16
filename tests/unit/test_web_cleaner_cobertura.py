"""Cobertura 100x100 de motor/core/web/cleaner/cleaner.py (TASK-20260815-003).

Cubre CleanedStats (propiedades removed/pct, to_dict, cero recibidos),
CleanedResult y DocumentCleaner.clean con documentos vacíos, cortos
(por debajo del mínimo) y válidos, con y sin texto.

Sin dependencias externas: solo motor.core.web + stdlib.
"""

from __future__ import annotations

from motor.core.web.cleaner.cleaner import CleanedResult, CleanedStats, DocumentCleaner
from motor.core.web.models import WebDocument


def _doc(url: str = "https://example.com/a", text: str = "contenido con varias palabras reales") -> WebDocument:
    return WebDocument(url=url, title="T", text=text, word_count=len(text.split()))


class TestCleanedStats:
    """Estadísticas de limpieza."""

    def test_documents_removed_suma_todos_los_tipos(self) -> None:
        stats = CleanedStats(
            documents_received=10,
            documents_removed_empty=2,
            documents_removed_duplicate_url=1,
            documents_removed_duplicate_hash=3,
        )
        assert stats.documents_removed == 6

    def test_documents_removed_cero(self) -> None:
        assert CleanedStats().documents_removed == 0

    def test_duplication_pct(self) -> None:
        stats = CleanedStats(documents_received=10, documents_removed_empty=2, documents_removed_duplicate_url=1)
        assert stats.duplication_pct == 30.0

    def test_duplication_pct_sin_recibidos(self) -> None:
        assert CleanedStats().duplication_pct == 0.0

    def test_to_dict(self) -> None:
        stats = CleanedStats(
            documents_received=4,
            documents_removed_empty=1,
            documents_removed_duplicate_url=1,
            documents_removed_duplicate_hash=1,
            documents_unique=1,
        )
        d = stats.to_dict()
        assert d["documents_received"] == 4
        assert d["documents_removed"] == 3
        assert d["documents_unique"] == 1
        assert d["duplication_pct"] == 75.0
        assert d["removed_empty"] == 1
        assert d["removed_duplicate_url"] == 1
        assert d["removed_duplicate_hash"] == 1

    def test_defaults(self) -> None:
        assert CleanedStats().documents_received == 0
        assert CleanedStats().documents_unique == 0


class TestCleanedResult:
    """Resultado del proceso de limpieza."""

    def test_defaults(self) -> None:
        r = CleanedResult()
        assert r.documents == []
        assert r.stats.documents_received == 0

    def test_con_valores(self) -> None:
        docs = [_doc()]
        stats = CleanedStats(documents_received=1)
        r = CleanedResult(documents=docs, stats=stats)
        assert r.documents == docs
        assert r.stats.documents_received == 1


class TestDocumentCleaner:
    """Limpieza de documentos."""

    def test_limpia_unicos(self) -> None:
        docs = [_doc("https://example.com/a"), _doc("https://example.com/b", "otro texto con palabras")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 2
        assert result.stats.documents_received == 2
        assert result.stats.documents_removed_empty == 0
        assert result.stats.documents_unique == 0  # unique lo fija dedup, no clean

    def test_elimina_vacios(self) -> None:
        docs = [_doc("https://example.com/a", text=""), _doc("https://example.com/b", "   ")]
        result = DocumentCleaner().clean(docs)
        assert result.documents == []
        assert result.stats.documents_removed_empty == 2

    def test_elimina_cortos_por_min_words(self) -> None:
        docs = [_doc("https://example.com/a", text="solo dos"), _doc("https://example.com/b", text="una")]
        result = DocumentCleaner(min_words=3).clean(docs)
        assert result.documents == []
        assert result.stats.documents_removed_empty == 2
        assert result.stats.documents_received == 2

    def test_normaliza_url(self) -> None:
        docs = [_doc("HTTPS://Example.COM/Path/", "texto con palabras suficientes")]
        result = DocumentCleaner().clean(docs)
        assert result.documents[0].url == "https://example.com/Path"

    def test_texto_con_espacios_se_recorta(self) -> None:
        docs = [_doc("https://example.com/a", text="  hola   mundo  prueba  texto  ")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 1
        assert result.documents[0].text == "hola   mundo  prueba  texto"

    def test_elimina_caracteres_restringidos(self) -> None:
        docs = [_doc("https://example.com/a", text="hola \x00mundo \x1fprueba  \x07texto extra")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 1
        assert result.documents[0].text == "hola mundo prueba  texto extra"

    def test_preserva_tabs_y_saltos_de_linea(self) -> None:
        docs = [_doc("https://example.com/a", text="linea1\nlinea2\tcolumna")]
        result = DocumentCleaner().clean(docs)
        assert result.documents[0].text == "linea1\nlinea2\tcolumna"

    def test_min_words_por_defecto_es_tres(self) -> None:
        docs = [_doc("https://example.com/a", text="tres palabras aquí")]
        result = DocumentCleaner().clean(docs)
        assert len(result.documents) == 1

    def test_lista_vacia(self) -> None:
        result = DocumentCleaner().clean([])
        assert result.documents == []
        assert result.stats.documents_received == 0
