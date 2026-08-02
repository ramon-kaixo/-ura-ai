"""Tests for scripts/pro/chaos_test.py."""

import asyncio

import scripts.pro.chaos_test as chaos


class TestCheckWarn:
    def test_check_pass(self):
        initial = chaos.PASS
        chaos.check("test", True, "detail")
        assert initial + 1 == chaos.PASS

    def test_check_fail(self):
        initial = chaos.FAIL
        chaos.check("test", False, "detail")
        assert initial + 1 == chaos.FAIL

    def test_warn(self):
        initial = chaos.WARN
        chaos.warn("test", "detail")
        assert initial + 1 == chaos.WARN

class TestMain:
    def test_list(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["chaos_test.py", "--list"])
        result = asyncio.run(chaos.main())
        assert result == 0

    def test_invalid_test(self, monkeypatch):
        monkeypatch.setattr("sys.argv", ["chaos_test.py", "no_existe", "--execute"])
        result = asyncio.run(chaos.main())
        assert result == 1
