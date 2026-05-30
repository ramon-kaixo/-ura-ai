#!/usr/bin/env python3
"""Tests for core/ura_maleta_manager.py (N2 Fase 1)."""

from __future__ import annotations


import pytest

from core.ura_maleta_manager import (
    Maleta,
    MaletaManager,
    MaletaValidationError,
    _cosine_similarity_lexical,
)


def _mk_data(maleta_id: str = "test_v1", tema: str = "algo") -> dict:
    return {
        "maleta_id": maleta_id,
        "version": 1,
        "creada_por": "manual",
        "fecha_creacion": "2026-05-05T00:00:00+00:00",
        "ultimo_uso": None,
        "confianza": 0.5,
        "tema": tema,
        "herramientas": {
            "buscadores": [{"nombre": "duckduckgo_text", "tipo": "web", "prioridad": 1}]
        },
        "fuentes_blancas": {"oficiales": [], "academicas": [], "especializadas": []},
        "formato_salida": {"estructura": {"titulo": "string"}},
    }


def test_validate_ok():
    mgr = MaletaManager()
    mgr.validate(_mk_data())


def test_validate_missing_fields():
    mgr = MaletaManager()
    data = _mk_data()
    del data["tema"]
    with pytest.raises(MaletaValidationError):
        mgr.validate(data)


def test_validate_empty_buscadores():
    mgr = MaletaManager()
    data = _mk_data()
    data["herramientas"]["buscadores"] = []
    with pytest.raises(MaletaValidationError):
        mgr.validate(data)


def test_validate_confianza_out_of_range():
    mgr = MaletaManager()
    data = _mk_data()
    data["confianza"] = 1.5
    with pytest.raises(MaletaValidationError):
        mgr.validate(data)


def test_save_and_load_roundtrip(tmp_path):
    mgr = MaletaManager(config_dir=tmp_path / "config", user_dir=tmp_path / "user")
    data = _mk_data("roundtrip_v1")
    maleta = Maleta(maleta_id=data["maleta_id"], tema=data["tema"], data=data)
    path = mgr.save(maleta)
    assert path.exists()
    loaded = mgr.load(path)
    assert loaded.maleta_id == "roundtrip_v1"
    assert loaded.confianza == 0.5


def test_update_confidence_with_success(tmp_path):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    data = _mk_data("conf_v1")
    maleta = Maleta(maleta_id=data["maleta_id"], tema=data["tema"], data=data)
    mgr.save(maleta)
    new = mgr.update_confidence(maleta, success=True)
    assert 0.5 < new <= 1.0


def test_update_confidence_with_explicit_score(tmp_path):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    data = _mk_data("score_v1")
    data["confianza"] = 0.5
    maleta = Maleta(maleta_id=data["maleta_id"], tema=data["tema"], data=data)
    mgr.save(maleta)
    new = mgr.update_confidence(maleta, success=True, score=1.0)
    # 0.5 * 0.7 + 1.0 * 0.3 = 0.65
    assert abs(new - 0.65) < 0.01


def test_cosine_similarity_lexical_basic():
    assert _cosine_similarity_lexical("hola mundo", "hola mundo") == 1.0
    assert _cosine_similarity_lexical("hola mundo", "chao") == 0.0
    sim = _cosine_similarity_lexical("fiscalidad autonomos", "fiscalidad empresas")
    assert 0 < sim < 1


def test_find_similar_returns_matches(tmp_path):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    # Disable embeddings for this test → fallback to Jaccard
    mgr._embedder = None
    data = _mk_data("m1", tema="fiscalidad autónomos España")
    mgr.save(Maleta(maleta_id="m1", tema=data["tema"], data=data))
    hits = mgr.find_similar("fiscalidad autónomos Cataluña", threshold=0.2)
    assert hits and hits[0][0].maleta_id == "m1"


def test_clone_emergency_creates_clone(tmp_path):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    data = _mk_data("base_v1", tema="fiscalidad autonomos espana")
    mgr.save(Maleta(maleta_id="base_v1", tema=data["tema"], data=data))
    # Patch similarity so it always returns 0.9
    mgr.similarity = lambda a, b: 0.9
    clone = mgr.clone_emergency("fiscalidad autonomos cataluna")
    assert clone is not None
    assert clone.confianza == 0.4
    assert "_clon_" in clone.maleta_id
    assert clone.data["__clon_origen__"]["maleta_id"] == "base_v1"
