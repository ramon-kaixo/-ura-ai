from __future__ import annotations

import pytest

from motor.core.secrets import (
    _clear_cache,
    get_secret,
    has_secret,
    list_available,
    require_secret,
)


class TestGetSecret:
    def test_env_var_found(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET_1", "magic-value")
        assert get_secret("TEST_SECRET_1") == "magic-value"

    def test_env_var_empty_falls_to_default(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET_2", "")
        assert get_secret("TEST_SECRET_2", default="fallback") == "fallback"

    def test_env_var_precedence_over_default(self, monkeypatch):
        monkeypatch.setenv("TEST_SECRET_3", "from-env")
        assert get_secret("TEST_SECRET_3", default="from-default") == "from-env"

    def test_no_env_no_file_returns_default(self, monkeypatch):
        monkeypatch.delenv("TEST_SECRET_NEVER_SET", raising=False)
        assert get_secret("TEST_SECRET_NEVER_SET", default="safe") == "safe"

    def test_no_env_no_file_no_default_returns_none(self, monkeypatch):
        monkeypatch.delenv("TEST_SECRET_ABSENT", raising=False)
        assert get_secret("TEST_SECRET_ABSENT") is None


class TestRequireSecret:
    def test_returns_value_when_present(self, monkeypatch):
        monkeypatch.setenv("REQUIRED_KEY", "found-it")
        assert require_secret("REQUIRED_KEY") == "found-it"

    def test_raises_keyerror_when_missing(self, monkeypatch):
        monkeypatch.delenv("MISSING_KEY", raising=False)
        _clear_cache()
        with pytest.raises(KeyError, match="MISSING_KEY"):
            require_secret("MISSING_KEY")


class TestHasSecret:
    def test_true_when_set(self, monkeypatch):
        monkeypatch.setenv("EXISTS", "yes")
        assert has_secret("EXISTS") is True

    def test_false_when_not_set(self, monkeypatch):
        monkeypatch.delenv("DOES_NOT_EXIST", raising=False)
        assert has_secret("DOES_NOT_EXIST") is False

    def test_false_when_empty(self, monkeypatch):
        monkeypatch.setenv("EMPTY_VAR", "")
        assert has_secret("EMPTY_VAR") is False


class TestListAvailable:
    def test_return_type(self):
        result = list_available()
        assert isinstance(result, list)
        assert result == sorted(result)

    def test_includes_set_secrets(self, monkeypatch):
        monkeypatch.setenv("GROQ_API_KEY", "sk-test")
        result = list_available()
        assert "GROQ_API_KEY" in result

    def test_excludes_unset_secrets(self, monkeypatch):
        monkeypatch.delenv("PYPI_TOKEN", raising=False)
        _clear_cache()
        assert "PYPI_TOKEN" not in list_available()


class TestDefaultBackend:
    def test_default_is_returned_for_unknown_secret(self, monkeypatch):
        monkeypatch.delenv("UNKNOWN_SECRET", raising=False)
        _clear_cache()
        assert get_secret("UNKNOWN_SECRET", default="backup") == "backup"

    def test_default_none_is_implicit(self, monkeypatch):
        monkeypatch.delenv("UNKNOWN_SECRET", raising=False)
        _clear_cache()
        assert get_secret("UNKNOWN_SECRET") is None
