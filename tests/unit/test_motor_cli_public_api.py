"""Tests para motor/cli/public_api.py — fachada pública del motor."""

from motor.cli import public_api


def test_exports_disponibles() -> None:
    for name in public_api.__all__:
        assert hasattr(public_api, name), f"falta {name}"


def test_algunos_tipos() -> None:
    assert public_api.UraConfig is not None
    assert public_api.QdrantClient is not None
    assert public_api.EventBus is not None
    assert public_api.HybridRetriever is not None
    assert public_api.format_prometheus is not None
    assert public_api.SYSTEM_STARTED is not None
