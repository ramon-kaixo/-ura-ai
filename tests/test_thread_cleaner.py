"""Tests for core/thread_cleaner.py — zombie thread cleaner with KILL_ALLOWED/REPORT_ONLY."""

import logging
from unittest.mock import MagicMock, patch


logging.disable(logging.CRITICAL)


class TestInstantiation:
    """ThreadCleaner se instancia sin errores."""

    def test_imports_without_error(self):
        from core.thread_cleaner import ThreadCleaner

        assert ThreadCleaner is not None

    def test_instantiates_without_error(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc is not None
        assert hasattr(tc, "config")
        assert hasattr(tc, "ura_processes")
        assert hasattr(tc, "stats")


class TestProtectedProcesses:
    """Procesos protegidos (NEVER_KILL) no se pueden matar."""

    def test_pid_1_is_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(1, "launchd")
        assert is_protected is True

    def test_launchd_is_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(9999, "launchd")
        assert is_protected is True

    def test_kernel_task_is_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(0, "kernel_task")
        assert is_protected is True

    def test_ollama_is_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(12345, "ollama")
        assert is_protected is True

    def test_docker_processes_are_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(8888, "com.docker.backend")
        assert is_protected is True

    def test_unknown_process_not_protected(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        is_protected, reason = tc._is_process_protected(99999, "unknown_zombie_process")
        assert is_protected is False


class TestUraProcessDetection:
    """Deteccion de procesos URA (KILL_ALLOWED)."""

    @patch("core.thread_cleaner.psutil.Process")
    def test_python3_is_ura_process(self, mock_process: MagicMock):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "python3"
        mock_proc.parent.return_value = None
        mock_process.return_value = mock_proc

        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_ura_process(99999, "python3") is True

    @patch("core.thread_cleaner.psutil.Process")
    def test_main_final_is_ura_process(self, mock_process: MagicMock):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "main_final"
        mock_proc.parent.return_value = None
        mock_process.return_value = mock_proc

        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_ura_process(99998, "main_final") is True

    @patch("core.thread_cleaner.psutil.Process")
    def test_unknown_not_ura_process(self, mock_process: MagicMock):
        mock_proc = MagicMock()
        mock_proc.name.return_value = "Safari"
        mock_proc.parent.return_value = None
        mock_process.return_value = mock_proc

        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_ura_process(99997, "Safari") is False


class TestExternalProcessDetection:
    """Procesos externos (REPORT_ONLY)."""

    def test_docker_is_external(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_external_process("docker") is True

    def test_redis_is_external(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_external_process("redis-server") is True

    def test_postgres_is_external(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_external_process("postgres") is True

    def test_ollama_not_external(self):
        from core.thread_cleaner import ThreadCleaner

        tc = ThreadCleaner()
        assert tc._is_external_process("ollama") is False


class TestDailyCounter:
    """Contador de kills diarios empieza en 0."""

    def test_stats_reset_daily(self):
        from core.thread_cleaner import ThreadCleaner
        from datetime import datetime

        tc = ThreadCleaner()
        today = datetime.now().strftime("%Y-%m-%d")
        assert tc.stats["date"] == today
        assert tc.stats["processes_killed_today"] == 0
        assert tc.stats["processes_reported_today"] == 0
        assert tc.stats["kill_attempts_failed"] == 0
