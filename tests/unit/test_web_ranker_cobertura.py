"""Cobertura 100x100 de motor/core/web/ranker/ranker.py (TASK-20260815-003).

Cubre RankingScore.total/to_dict, RankedDocument (final_score,
score_breakdown), DocumentRanker con pesos por defecto y custom,
coincidencias en título/URL/texto, bonus canónico, penalizaciones short/
empty, posiciones, empates (tiebreak por URL) y metadatos no-dict.

Sin dependencias externas: solo motor.core.web + stdlib.
"""

from __future__ import annotations

from motor.core.web.models import WebDocument
from motor.core.web.ranker.ranker import DEFAULT_WEIGHTS, DocumentRanker, RankedDocument, RankingScore


def _doc(
    url: str,
    title: str = "",
    text: str = "",
    *,
    quality: float = 1.0,
    word_count: int | None = None,
    metadata: dict[str, str] | None = None,
) -> WebDocument:
    wc = word_count if word_count is not None else len(text.split())
    return WebDocument(url=url, title=title, text=text, word_count=wc, quality_score=quality, metadata=metadata)


class TestRankingScore:
    """Puntuación descomponible."""

    def test_total_suma_todos_los_factores(self) -> None:
        s = RankingScore(
            quality=1.0,
            position=0.5,
            length=0.25,
            title_match=0.75,
            url_match=0.5,
            text_match=0.25,
            canonical_bonus=0.5,
            short_penalty=-2.0,
            empty_penalty=-5.0,
        )
        assert s.total == round(1.0 + 0.5 + 0.25 + 0.75 + 0.5 + 0.25 + 0.5 - 2.0 - 5.0, 6)

    def test_total_defaults(self) -> None:
        assert RankingScore().total == 0.0

    def test_to_dict(self) -> None:
        s = RankingScore(quality=1.23456, position=0.5)
        d = s.to_dict()
        assert d["quality"] == 1.2346
        assert d["position"] == 0.5
        assert d["total"] == s.total
        assert set(d) == {
            "quality",
            "position",
            "length",
            "title_match",
            "url_match",
            "text_match",
            "canonical_bonus",
            "short_penalty",
            "empty_penalty",
            "total",
        }


class TestRankedDocument:
    """Documento rankeado."""

    def test_final_score(self) -> None:
        doc = _doc("https://example.com/a", text="un texto")
        rd = RankedDocument(document=doc, score=RankingScore(quality=3.0))
        assert rd.final_score == 3.0

    def test_score_breakdown(self) -> None:
        doc = _doc("https://example.com/a", text="un texto")
        rd = RankedDocument(document=doc)
        assert rd.score_breakdown == RankingScore().to_dict()

    def test_score_por_defecto(self) -> None:
        doc = _doc("https://example.com/a", text="un texto")
        rd = RankedDocument(document=doc)
        assert isinstance(rd.score, RankingScore)


class TestDocumentRanker:
    """Ranking de documentos."""

    def test_weights_por_defecto(self) -> None:
        r = DocumentRanker()
        assert r.weights == DEFAULT_WEIGHTS

    def test_weights_custom(self) -> None:
        r = DocumentRanker(weights={"quality": 10.0})
        assert r.weights["quality"] == 10.0
        assert r.weights["position"] == DEFAULT_WEIGHTS["position"]

    def test_rank_ordena_por_total_descendente(self) -> None:
        a = _doc("https://example.com/b", text="python es un lenguaje de programación popular y usado", quality=0.2)
        b = _doc("https://example.com/a", text="python avanzado en profundidad para expertos del lenguaje", quality=0.9)
        ranked = DocumentRanker().rank("python", [a, b])
        assert ranked[0].document is b
        assert ranked[1].document is a

    def test_rank_tiebreak_por_url(self) -> None:
        a = _doc("https://example.com/z", text="texto idéntico para comparar el desempate exacto", quality=0.5)
        b = _doc("https://example.com/a", text="texto idéntico para comparar el desempate exacto", quality=0.5)
        # misma posición para ambos: empate real, desempata la URL ascendente
        ranked = DocumentRanker().rank("texto", [a, b], positions={"https://example.com/z": 0, "https://example.com/a": 0})
        assert ranked[0].document.url == "https://example.com/a"
        assert ranked[1].document.url == "https://example.com/z"

    def test_rank_respeta_posiciones(self) -> None:
        a = _doc("https://example.com/a", text="contenido del documento a", quality=0.5)
        b = _doc("https://example.com/b", text="contenido del documento b", quality=0.5)
        ranked = DocumentRanker().rank("contenido", [a, b], positions={a.url: 0, b.url: 100})
        assert ranked[0].document is a

    def test_rank_sin_posiciones_usa_indice(self) -> None:
        a = _doc("https://example.com/a", text="contenido documento", quality=0.5)
        b = _doc("https://example.com/b", text="contenido documento", quality=0.5)
        r = DocumentRanker()
        ranked_a = r.rank("contenido", [a, b])
        ranked_b = r.rank("contenido", [b, a])
        assert ranked_a[0].document.url != ranked_b[0].document.url

    def test_rank_lista_vacia(self) -> None:
        assert DocumentRanker().rank("q", []) == []

    def test_rank_query_sin_terminos(self) -> None:
        a = _doc("https://example.com/a", text="euro símbolo ñ", quality=0.5)
        ranked = DocumentRanker().rank("???", [a])
        assert len(ranked) == 1
        assert ranked[0].score.total == round(
            ranked[0].score.quality
            + ranked[0].score.position
            + ranked[0].score.length
            + ranked[0].score.short_penalty
            + ranked[0].score.empty_penalty,
            6,
        )

    def test_short_y_empty_penalty(self) -> None:
        short = _doc("https://example.com/short", text="cortísimo", word_count=5)
        long = _doc("https://example.com/long", text="a" * 2000, word_count=2000)
        ranked = DocumentRanker().rank("a", [short, long])
        assert ranked[0].document is long
        assert ranked[1].score.short_penalty < 0
        assert ranked[1].score.empty_penalty < 0

    def test_canonical_bonus(self) -> None:
        doc = _doc("https://example.com/a", text="contenido", metadata={"canonical_url": "https://canon"})
        ranked = DocumentRanker().rank("contenido", [doc])
        assert ranked[0].score.canonical_bonus == DEFAULT_WEIGHTS["canonical_bonus"]

    def test_sin_canonical_no_hay_bonus(self) -> None:
        doc = _doc("https://example.com/a", text="contenido", metadata={})
        ranked = DocumentRanker().rank("contenido", [doc])
        assert ranked[0].score.canonical_bonus == 0.0

    def test_metadata_no_dict_no_hay_bonus(self) -> None:
        doc = _doc("https://example.com/a", text="contenido", metadata=None)
        ranked = DocumentRanker().rank("contenido", [doc])
        assert ranked[0].score.canonical_bonus == 0.0

    def test_word_count_de_texto_si_no_explicito(self) -> None:
        doc = WebDocument(url="https://example.com/a", title="", text="tres palabras juntas", word_count=0)
        ranked = DocumentRanker().rank("palabras", [doc])
        assert ranked[0].score.length > 0.0

    def test_componentes_matching(self) -> None:
        doc = _doc(
            "https://python.org/tutorial",
            title="Guía de python",
            text="aprende python con la guía de python básico y avanzado",
        )
        ranked = DocumentRanker().rank("python", [doc])
        score = ranked[0].score
        assert score.title_match > 0
        assert score.url_match > 0
        assert score.text_match > 0
