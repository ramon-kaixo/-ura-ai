"""Tests para motor/events/compat.py — compatibilidad de API de plugins."""
from __future__ import annotations
import pytest

from motor.events.compat import check_api_compatibility, check_plugin_dependency


class TestCheckApiCompatibility:
    @pytest.mark.unit
    def test_sin_version_legacy(self) -> None:
        assert check_api_compatibility("", "1.0.0") is True

    @pytest.mark.unit
    def test_sin_version_sin_legacy(self) -> None:
        assert check_api_compatibility("", "1.0.0", allow_legacy=False) is False

    @pytest.mark.unit
    def test_major_igual_minor_menor(self) -> None:
        assert check_api_compatibility("1.2.0", "1.5.0") is True

    @pytest.mark.unit
    def test_major_igual_minor_igual(self) -> None:
        assert check_api_compatibility("1.5.0", "1.5.0") is True

    @pytest.mark.unit
    def test_major_distinto(self) -> None:
        assert check_api_compatibility("2.0.0", "1.5.0") is False

    @pytest.mark.unit
    def test_minor_plugin_mayor(self) -> None:
        assert check_api_compatibility("1.6.0", "1.5.0") is False

    @pytest.mark.unit
    def test_version_invalida(self) -> None:
        assert check_api_compatibility("abc", "1.0.0") is False
        assert check_api_compatibility("1.0.0", None) is False


class TestCheckPluginDependency:
    @pytest.mark.unit
    def test_sin_spec(self) -> None:
        assert check_plugin_dependency("dep", "", "1.0.0") is True
        assert check_plugin_dependency("dep", "*", "1.0.0") is True

    @pytest.mark.unit
    def test_ge(self) -> None:
        assert check_plugin_dependency("dep", ">=1.2.0", "1.3.0") is True
        assert check_plugin_dependency("dep", ">=1.2.0", "1.1.0") is False

    @pytest.mark.unit
    def test_eq(self) -> None:
        assert check_plugin_dependency("dep", "==1.2.0", "1.2.0") is True
        assert check_plugin_dependency("dep", "==1.2.0", "1.2.1") is False

    @pytest.mark.unit
    def test_lt(self) -> None:
        assert check_plugin_dependency("dep", "<2.0.0", "1.9.0") is True
        assert check_plugin_dependency("dep", "<2.0.0", "2.0.0") is False

    @pytest.mark.unit
    def test_rango(self) -> None:
        """Formato funcional: '>=1.0.0 <2.0.0' (sin coma)."""
        assert check_plugin_dependency("dep", ">=1.0.0 <2.0.0", "1.5.0") is True
        assert check_plugin_dependency("dep", ">=1.0.0 <2.0.0", "2.0.0") is False
        assert check_plugin_dependency("dep", ">=1.0.0 <2.0.0", "0.9.0") is False

    @pytest.mark.unit
    def test_compatible(self) -> None:
        assert check_plugin_dependency("dep", "~=1.2", "1.5.0") is True
        assert check_plugin_dependency("dep", "~=1.2", "2.0.0") is False
        assert check_plugin_dependency("dep", "~=2", "2.5.0") is True
        assert check_plugin_dependency("dep", "~=2", "3.0.0") is False

    @pytest.mark.unit
    def test_spec_desconocida_acepta(self) -> None:
        assert check_plugin_dependency("dep", "^1.0.0", "0.1.0") is True

    @pytest.mark.unit
    def test_version_invalida_parse(self) -> None:
        assert check_plugin_dependency("dep", ">=1.0", "no-version") is False
