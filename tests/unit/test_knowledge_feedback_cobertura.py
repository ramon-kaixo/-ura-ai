"""Tests de cobertura para knowledge/engine/feedback.py."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from knowledge.engine.feedback import (
    Feedback,
    InvalidDocIdError,
    _validate_doc_id,
    apply_ranking_overlay,
    get_feedback,
    record_feedback,
    top_rated,
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS op_feedback_agg (
    doc_id           TEXT PRIMARY KEY,
    n_ratings        INTEGER NOT NULL DEFAULT 0,
    avg_rating       REAL NOT NULL DEFAULT 0.0,
    last_feedback_at TEXT,
    updated_at       TEXT
);
"""


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "fb.db"
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    return path


D1 = "0123456789ab"


def test_invalid_doc_id_error() -> None:
    assert issubclass(InvalidDocIdError, ValueError)


@pytest.mark.parametrize(
    "doc_id",
    ["", "abc", "0123456789abX", "0123456789abcdef"],
)
def test_validate_doc_id_invalidos(doc_id) -> None:
    with pytest.raises(InvalidDocIdError):
        _validate_doc_id(doc_id)


def test_validate_doc_id_valido() -> None:
    _validate_doc_id(D1)


def test_validate_doc_id_none() -> None:
    with pytest.raises(InvalidDocIdError):
        _validate_doc_id(None)


def test_record_rating_fuera_de_rango(db_path) -> None:
    assert record_feedback(db_path, D1, 0) is False
    assert record_feedback(db_path, D1, 6) is False


def test_record_doc_id_invalido(db_path) -> None:
    assert record_feedback(db_path, "bad", 3) is False


def test_record_nuevo_y_media(db_path) -> None:
    assert record_feedback(db_path, D1, 2) is True
    assert record_feedback(db_path, D1, 4) is True
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT n_ratings, avg_rating FROM op_feedback_agg WHERE doc_id=?", (D1,)).fetchone()
    conn.close()
    assert row["n_ratings"] == 2
    assert row["avg_rating"] == pytest.approx(3.0)


def test_record_error(db_path, tmp_path) -> None:
    assert record_feedback(tmp_path / "no.db", D1, 3) is False


def test_get_feedback(db_path) -> None:
    record_feedback(db_path, D1, 5)
    fb = get_feedback(db_path, D1)
    assert fb is not None
    assert fb.doc_id == D1
    assert fb.rating == 5
    assert fb.timestamp


def test_get_feedback_no_existe(db_path) -> None:
    assert get_feedback(db_path, D1) is None


def test_get_feedback_invalido(db_path) -> None:
    assert get_feedback(db_path, "xx") is None


def test_get_feedback_error(tmp_path) -> None:
    assert get_feedback(tmp_path / "no.db", D1) is None


def test_overlay_vacio() -> None:
    assert apply_ranking_overlay([], "/no/existe") == []


def test_overlay_sin_feedback(db_path) -> None:
    results = [{"doc_id": D1, "score": 1.0}]
    out = apply_ranking_overlay(results, db_path)
    assert out[0]["score"] == pytest.approx(1.0)
    assert out[0]["avg_rating"] == 3.0
    assert out[0]["n_ratings"] == 0
    assert results[0] == {"doc_id": D1, "score": 1.0}  # no muta original


def test_overlay_con_feedback(db_path) -> None:
    record_feedback(db_path, D1, 5)
    out = apply_ranking_overlay([{"doc_id": D1, "score": 1.0}], db_path)
    assert out[0]["score"] == pytest.approx(1.4)
    assert out[0]["avg_rating"] == 5.0
    assert out[0]["n_ratings"] == 1


def test_overlay_ordena_y_varios(db_path) -> None:
    d2 = "0123456789ac"
    record_feedback(db_path, D1, 5)
    record_feedback(db_path, d2, 1)
    out = apply_ranking_overlay(
        [{"doc_id": d2, "score": 2.0}, {"doc_id": D1, "score": 2.0}],
        db_path,
    )
    assert out[0]["doc_id"] == D1
    assert out[1]["doc_id"] == d2


def test_overlay_error(tmp_path) -> None:
    out = apply_ranking_overlay([{"doc_id": D1, "score": 1.0}], tmp_path / "no.db")
    assert out == [{"doc_id": D1, "score": 1.0}]


def test_top_rated(db_path) -> None:
    d2 = "0123456789ac"
    record_feedback(db_path, D1, 5)
    record_feedback(db_path, d2, 1)
    tops = top_rated(db_path, limit=1)
    assert len(tops) == 1
    assert tops[0].doc_id == D1
    assert tops[0].rating == 5


def test_top_rated_vacio(db_path) -> None:
    assert top_rated(db_path) == []


def test_top_rated_error(tmp_path) -> None:
    assert top_rated(tmp_path / "no.db") == []


def test_feedback_dataclass() -> None:
    fb = Feedback(doc_id=D1, rating=4, timestamp="t")
    assert fb.timestamp == "t"
