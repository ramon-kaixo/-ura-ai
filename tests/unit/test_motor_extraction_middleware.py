"""Tests para motor/core/fusion/stages/extraction.py y motor/assistant/api/middleware.py."""
from __future__ import annotations

import time
from types import SimpleNamespace
from unittest import mock

import pytest

from motor.assistant.api.middleware import _RateLimiter, _scoped_cid
from motor.core.fusion.models import FusionContext
from motor.core.fusion.stages.extraction import ExtractionStage


class FakeEvidence:
    def __init__(self, evidence_id="ev1", fragment="texto", quality_score=0.8, fetched_at="2026-01-01T00:00:00Z"):
        self.evidence_id = evidence_id
        self.fragment = fragment
        self.quality_score = quality_score
        self.fetched_at = fetched_at


class TestExtractionStage:
    def test_meta(self) -> None:
        s = ExtractionStage()
        assert s.name == "ExtractionStage"
        assert s.version == "1.0.0"
        assert s.stage.value == "extraction"

    def test_sin_bundle(self) -> None:
        s = ExtractionStage()
        ctx = FusionContext(bundle=None)
        out = s._execute(ctx)
        assert out.claims == []

    def test_extrae_claims(self) -> None:
        s = ExtractionStage()
        bundle = SimpleNamespace(evidence=[FakeEvidence("ev1", "texto uno", 0.9), FakeEvidence("ev2", "texto dos", 0.5)])
        ctx = FusionContext(bundle=bundle)
        out = s._execute(ctx)
        assert len(out.claims) == 2
        c = out.claims[0]
        assert c.text == "texto uno"
        assert c.confidence == 0.9
        assert c.evidence.evidence_id == "ev1"
        assert c.text_id == "ev1"
        assert out.statistics["claims_extracted"] == 2

    def test_claim_id_unico(self) -> None:
        s = ExtractionStage()
        bundle = SimpleNamespace(evidence=[FakeEvidence("ev1", "texto"), FakeEvidence("ev1", "texto")])
        ctx = FusionContext(bundle=bundle)
        out = s._execute(ctx)
        # mismo evidence_id + fragment -> mismo claim id
        assert out.claims[0].id == out.claims[1].id


class TestRateLimiter:
    def test_primer_request_ok(self) -> None:
        rl = _RateLimiter()
        rl.check("user1")  # no debe lanzar

    def test_multiples_ok(self) -> None:
        rl = _RateLimiter()
        for _ in range(5):
            rl.check("u")

    def test_limite_excedido(self, monkeypatch) -> None:
        from fastapi import HTTPException

        rl = _RateLimiter()
        rl._requests["u"] = [time.monotonic()] * 60  # lleno
        with pytest.raises(HTTPException) as e:
            rl.check("u")
        assert e.value.status_code == 429

    def test_ventana_limpia_viejos(self, monkeypatch) -> None:
        rl = _RateLimiter()
        # request viejos (fuera de ventana 60s)
        monkeypatch.setattr("motor.assistant.api.middleware.time.monotonic", lambda: 100.0)
        rl.check("u")
        monkeypatch.setattr("motor.assistant.api.middleware.time.monotonic", lambda: 200.0)
        rl._requests["u"] = [50.0] * 59  # viejos
        rl.check("u")  # limpia los 59 viejos, queda 1 -> no excede

    def test_singleton(self) -> None:
        from motor.assistant.api.middleware import _rate_limiter

        assert isinstance(_rate_limiter, _RateLimiter)


class TestScopedCid:
    def test_con_user(self) -> None:
        cid = _scoped_cid("user-1234567890abcdef", "conv1")
        assert cid == "usr_user-1234567890a__conv1"

    def test_sin_user(self) -> None:
        assert _scoped_cid("", "conv1") == "conv1"

    def test_user_largo_truncado(self) -> None:
        cid = _scoped_cid("x" * 50, "c")
        assert len(cid.split("__")[0]) <= 20
