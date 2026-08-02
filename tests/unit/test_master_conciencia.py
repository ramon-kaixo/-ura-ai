"""Tests for scripts/pro/master_conciencia.py."""

import json
from unittest.mock import MagicMock, patch

import pytest

import scripts.pro.master_conciencia as mc


class TestConfig:
    def test_gx10_default(self):
        assert mc.GX10 == "10.164.1.99"

    def test_log_path(self):
        assert mc.LOG.name == "master_conciencia.log"

    def test_test_actions_count(self):
        assert len(mc.TEST_ACTIONS) == 8


class TestTestApi:
    @patch("scripts.pro.master_conciencia.urllib.request.urlopen")
    def test_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": True, "resultado": "done"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = mc.test_api("test", {"name": "x"})
        assert result is True

    @patch("scripts.pro.master_conciencia.urllib.request.urlopen")
    def test_fail(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({"ok": False, "error": "boom"}).encode()
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = mc.test_api("test", {"name": "x"})
        assert result is False

    @patch("scripts.pro.master_conciencia.urllib.request.urlopen", side_effect=Exception("timeout"))
    def test_error(self, mock_urlopen):
        result = mc.test_api("test", {"name": "x"})
        assert result is False


class TestMain:
    @patch("scripts.pro.master_conciencia.urllib.request.urlopen", side_effect=Exception("no mcp"))
    def test_mcp_no_responde(self, mock_urlopen):
        with pytest.raises(SystemExit) as exc:
            mc.main()
        assert exc.value.code == 1
