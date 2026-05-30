#!/usr/bin/env python3
"""Tests for core/ura_observational_learner.py."""

from __future__ import annotations

import json

import pytest

from core.ura_maleta_manager import MaletaManager
from core.ura_observational_learner import (
    ObservationalLearner,
    _slugify,
)


def _n3_payload(tema: str, urls: list[str]) -> dict:
    return {
        "tema": tema,
        "nivel": "N3",
        "estado": "ok",
        "resultados": [
            {
                "titulo": f"R{i}",
                "url": u,
                "snippet": "ok",
                "fuente": "test",
                "score_relevancia": 0.7,
            }
            for i, u in enumerate(urls)
        ],
        "razonamiento": "razonamiento de prueba",
        "modelo": "test_model",
    }


def test_slugify_handles_spaces_and_accents():
    assert _slugify("Hola Mundo") == "hola_mundo"
    assert _slugify("  fiscalidad   autónomos!! ") == "fiscalidad_autónomos"


@pytest.mark.asyncio
async def test_observe_below_threshold_does_not_promote(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)

    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    for i in range(5):  # menos del umbral (10)
        result = await learner.observe(
            "tema dummy",
            _n3_payload("tema dummy", [f"https://x.com/{i}"]),
        )
    assert result.promoted is False
    assert result.observations_count == 5
    assert "insuficientes" in result.razon.lower()


@pytest.mark.asyncio
async def test_observe_promotes_after_threshold_no_n2_runner(tmp_path, monkeypatch):
    """Sin n2_runner, examen omitido → promoción directa al llegar a 10."""
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)

    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    last = None
    for i in range(10):
        last = await learner.observe(
            "tema novedoso",
            _n3_payload("tema novedoso", [f"https://x.com/{i}"]),
        )
    assert last.promoted is True
    assert last.maleta_id and last.maleta_id.startswith("learned_")
    # Verificar que se persistió la maleta
    loaded = mgr.find_by_id(last.maleta_id)
    assert loaded is not None
    assert loaded.confianza < 1.0


@pytest.mark.asyncio
async def test_observe_promotes_with_n2_examen_pasa(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)
    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    common_urls = [f"https://x.com/{i}" for i in range(5)]

    async def fake_n2(tema, maleta):
        # Devuelve EXACTAMENTE las mismas URLs → score 1.0
        return {
            "results": [{"url": u, "titulo": "T"} for u in common_urls],
        }

    last = None
    for _ in range(10):
        last = await learner.observe(
            "tema con examen",
            _n3_payload("tema con examen", common_urls),
            n2_runner=fake_n2,
        )
    assert last.promoted is True
    assert last.score_examen >= 0.85


@pytest.mark.asyncio
async def test_observe_does_not_promote_if_examen_falla(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)
    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    n3_urls = [f"https://x.com/{i}" for i in range(5)]

    async def fake_n2_distinto(tema, maleta):
        # URLs totalmente distintas → score 0.0
        return {
            "results": [{"url": f"https://otro.com/{i}", "titulo": "T"} for i in range(5)],
        }

    last = None
    for _ in range(10):
        last = await learner.observe(
            "tema con examen fallido",
            _n3_payload("tema con examen fallido", n3_urls),
            n2_runner=fake_n2_distinto,
        )
    assert last.promoted is False
    assert "fallido" in last.razon.lower() or "examen" in last.razon.lower()
    assert last.score_examen < 0.85


@pytest.mark.asyncio
async def test_observation_persists_to_disk(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)
    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    await learner.observe("tema persistente", _n3_payload("tema persistente", ["https://a"]))
    files = list((tmp_path / "obs").glob("*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text(encoding="utf-8"))
    assert len(data) == 1
    assert data[0]["tema"] == "tema persistente"


@pytest.mark.asyncio
async def test_error_n3_payload_not_observed(tmp_path, monkeypatch):
    mgr = MaletaManager(config_dir=tmp_path / "c", user_dir=tmp_path / "u")
    monkeypatch.setattr("core.ura_observational_learner.get_maleta_manager", lambda: mgr)
    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    learner.maleta_mgr = mgr

    bad = {"tema": "x", "estado": "error", "resultados": []}
    result = await learner.observe("x", bad)
    assert result.promoted is False
    assert "no se observa" in result.razon.lower()


def test_stats_reports_counts(tmp_path):
    learner = ObservationalLearner(observations_dir=tmp_path / "obs")
    stats = learner.stats()
    assert stats["topics_tracked"] == 0
    assert stats["min_observations"] == 10
