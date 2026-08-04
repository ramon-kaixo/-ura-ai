from __future__ import annotations

import pytest

from motor.core.executor import SubprocessExecutor


class TestSubprocessExecutorSync:
    def test_successful_command(self):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "hello_f10"])
        assert result.ok is True
        assert result.returncode == 0
        assert "hello_f10" in result.stdout

    def test_stdout_captured(self):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "stdout_test_f10"])
        assert result.stdout.strip() == "stdout_test_f10"

    def test_stderr_captured(self):
        executor = SubprocessExecutor()
        result = executor.run(["bash", "-c", "echo stderr_f10 >&2; echo stdout_f10"])
        assert result.ok is True
        assert "stdout_f10" in result.stdout
        assert "stderr_f10" in result.stderr

    def test_non_zero_returncode(self):
        executor = SubprocessExecutor()
        result = executor.run(["bash", "-c", "exit 42"])
        assert result.ok is False
        assert result.returncode == 42

    def test_timeout(self):
        executor = SubprocessExecutor()
        result = executor.run(["sleep", "10"], timeout=1)
        assert result.ok is False
        assert result.timed_out is True
        assert "Timeout" in result.error
        assert result.returncode == -1

    def test_command_not_found(self):
        executor = SubprocessExecutor()
        result = executor.run(["nonexistent_cmd_xyz_f10"])
        assert result.ok is False
        assert result.returncode == -1

    def test_cwd_respected(self):
        executor = SubprocessExecutor()
        result = executor.run(["pwd"], cwd="/tmp")
        assert result.ok is True
        assert result.stdout.strip() == "/tmp"

    def test_cmd_is_recorded(self):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "a", "b"])
        assert list(result.cmd) == ["echo", "a", "b"]

    def test_duration_ms_set(self):
        executor = SubprocessExecutor()
        result = executor.run(["echo", "fast"])
        assert result.duration_ms > 0

    def test_error_on_failure(self):
        executor = SubprocessExecutor()
        result = executor.run(["bash", "-c", "echo err_msg >&2; exit 1"])
        assert result.ok is False
        assert "err_msg" in result.error


class TestSubprocessExecutorAsync:
    @pytest.mark.asyncio
    async def test_async_successful(self):
        executor = SubprocessExecutor()
        result = await executor.arun(["echo", "async_hello_f10"])
        assert result.ok is True
        assert "async_hello_f10" in result.stdout

    @pytest.mark.asyncio
    async def test_async_timeout(self):
        executor = SubprocessExecutor()
        result = await executor.arun(["sleep", "10"], timeout=1)
        assert result.ok is False
        assert result.timed_out is True
        assert "Timeout" in result.error
        assert result.returncode == -1

    @pytest.mark.asyncio
    async def test_async_command_not_found(self):
        executor = SubprocessExecutor()
        result = await executor.arun(["nonexistent_cmd_async_f10"])
        assert result.ok is False
        assert result.returncode == -1

    @pytest.mark.asyncio
    async def test_async_non_zero_returncode(self):
        executor = SubprocessExecutor()
        result = await executor.arun(["bash", "-c", "exit 7"])
        assert result.ok is False
        assert result.returncode == 7

    @pytest.mark.asyncio
    async def test_async_stdout_stderr(self):
        executor = SubprocessExecutor()
        result = await executor.arun(["bash", "-c", "echo out_async; echo err_async >&2"])
        assert result.ok is True
        assert "out_async" in result.stdout
        assert "err_async" in result.stderr or "err_async" in result.error


class TestSubprocessExecutorIntegration:
    def test_executor_used_by_motors(self):
        from motor.core.executor import SubprocessExecutor

        executor = SubprocessExecutor()
        result = executor.run(["python3", "--version"])
        assert result.ok is True
        assert "Python" in result.stdout

    def test_graceful_handling_of_empty_cmd(self):
        executor = SubprocessExecutor()
        result = executor.run([])
        assert result.ok is False
