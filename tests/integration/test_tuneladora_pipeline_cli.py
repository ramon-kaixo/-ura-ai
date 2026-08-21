"""Tests for the tuneladora CLI entry point (scripts/pro/tuneladora/tuneladora_pipeline.py)."""

from __future__ import annotations

from unittest import mock

from scripts.pro.tuneladora.tuneladora_pipeline import cmd_pending, cmd_stats, main


class TestCmdPending:
    def test_no_pending(self, capsys):
        with mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.PendingQueue") as mq:
            mq.return_value.list_pending.return_value = []
            cfg = mock.Mock()
            cmd_pending(cfg)
            captured = capsys.readouterr()
            assert "No pending fixes" in captured.out

    def test_with_pending(self, capsys):
        with mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.PendingQueue") as mq:
            mq.return_value.list_pending.return_value = [
                {"id": 1, "estado": "pendiente", "herramienta": "ruff", "archivo": "test.py", "error_raw": "F821"},
            ]
            cfg = mock.Mock()
            cmd_pending(cfg)
            captured = capsys.readouterr()
            assert "test.py" in captured.out


class TestCmdStats:
    def test_output_format(self, capsys):
        with mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.PendingQueue") as mq:
            mq.return_value.stats.return_value = {"pending_fixes": 3, "total_runs": 10, "ok_runs": 8, "fail_runs": 2}
            cfg = mock.Mock()
            cmd_stats(cfg)
            captured = capsys.readouterr()
            assert "Pending fixes" in captured.out
            assert "Total runs" in captured.out
            assert "OK runs" in captured.out


class TestMainEntry:
    def test_pending_flag(self):
        with (
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.cmd_pending") as m,
            mock.patch("sys.argv", ["prog", "--pending"]),
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.Configuration"),
        ):
            main()
            m.assert_called_once()

    def test_stats_flag(self):
        with (
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.cmd_stats") as m,
            mock.patch("sys.argv", ["prog", "--stats"]),
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.Configuration"),
        ):
            main()
            m.assert_called_once()

    def test_rollback_flag(self):
        with (
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.cmd_rollback") as m,
            mock.patch("sys.argv", ["prog", "--rollback"]),
            mock.patch("scripts.pro.tuneladora.tuneladora_pipeline.Configuration"),
        ):
            main()
            m.assert_called_once()
