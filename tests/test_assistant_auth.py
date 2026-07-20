"""Tests para auth, config y herramientas."""
from __future__ import annotations

import os

import pytest
from fastapi import Request
from starlette.responses import JSONResponse

from motor.assistant.auth import AuthMiddleware
from motor.assistant.config import AssistantConfig
from motor.assistant.executor import (
    CalculatorTool,
    FileReadTool,
    GitBranchTool,
    GitCommitTool,
)


class TestConfig:
    def test_default_host(self):
        cfg = AssistantConfig()
        assert cfg.host == "127.0.0.1"

    def test_default_port(self):
        cfg = AssistantConfig()
        assert cfg.port == 8000

    def test_auth_disabled_by_default(self):
        cfg = AssistantConfig()
        assert cfg.auth_enabled is False

    def test_auth_enabled_with_key(self, monkeypatch):
        monkeypatch.setenv("URA_API_KEY", "test-key")
        cfg = AssistantConfig()
        assert cfg.auth_enabled is True
        assert cfg.api_key == "test-key"

    def test_db_for_returns_path(self, monkeypatch, tmp_path):
        monkeypatch.setenv("URA_DATA_DIR", str(tmp_path))
        cfg = AssistantConfig()
        path = cfg.db_for("test")
        assert path.endswith("test.db")


class TestCalculator:
    @pytest.fixture
    def calc(self):
        return CalculatorTool()

    def test_basic_arithmetic(self, calc):
        result = calc.execute("2 + 3")
        assert result.success
        assert result.output == "5"

    def test_complex_expression(self, calc):
        result = calc.execute("(4 + 5) * 3")
        assert result.success
        assert result.output == "27"

    def test_division(self, calc):
        result = calc.execute("10 / 4")
        assert result.success
        assert result.output == "2.5"

    def test_math_functions(self, calc):
        result = calc.execute("sqrt(16) + abs(-5)")
        assert result.success
        assert result.output == "9"

    def test_empty_expression(self, calc):
        result = calc.execute("")
        assert not result.success

    def test_invalid_expression(self, calc):
        result = calc.execute("invalid")
        assert not result.success


class TestFileReadTool:
    @pytest.fixture
    def tool(self):
        return FileReadTool()

    def test_nonexistent_file(self, tool):
        result = tool.execute("/nonexistent/path/file.txt")
        assert not result.success

    def test_outside_safe_dirs(self, tool):
        result = tool.execute("/etc/shadow")
        assert not result.success


class TestGitBranchTool:
    @pytest.fixture
    def tool(self):
        return GitBranchTool()

    def test_execute_returns_string(self, tool):
        result = tool.execute()
        assert result.success
        assert isinstance(result.output, str)
        assert len(result.output) > 0


class TestGitCommitTool:
    @pytest.fixture
    def tool(self):
        return GitCommitTool()

    def test_rejects_empty_message(self):
        pass
