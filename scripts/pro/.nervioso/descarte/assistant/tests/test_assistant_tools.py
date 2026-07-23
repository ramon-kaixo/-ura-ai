"""Tests for motor/assistant/tools.py — ToolOrchestrator."""

from __future__ import annotations

from motor.assistant.models import UserIntent
from motor.assistant.tools import GitLogTool, GitStatusTool, ShellTool, ToolOrchestrator


class TestToolAdapters:
    def test_git_status_name(self):
        tool = GitStatusTool()
        assert tool.name() == "git_status"

    def test_git_log_name(self):
        tool = GitLogTool()
        assert tool.name() == "git_log"

    def test_shell_name(self):
        tool = ShellTool()
        assert tool.name() == "shell"

    def test_shell_empty_command(self):
        tool = ShellTool()
        result = tool.run({"command": ""})
        assert "error" in result


class TestToolOrchestrator:
    def setup_method(self):
        self.orc = ToolOrchestrator()

    def test_list_tools(self):
        tools = self.orc.list_tools()
        assert len(tools) >= 3

    def test_select_tool_command(self):
        tool = self.orc.select_tool(UserIntent.COMMAND, {"original_text": "git status"})
        assert tool is not None

    def test_select_tool_chat(self):
        tool = self.orc.select_tool(UserIntent.CHAT, {})
        assert tool is None

    def test_execute_no_tool_found(self):
        result = self.orc.execute(UserIntent.CHAT, {"original_text": "hola"})
        assert "error" in result

    def test_execute_command(self):
        from motor.assistant.tools import ShellTool

        tool = ShellTool()
        result = tool.run({"command": ["echo", "hello"]})
        assert isinstance(result, dict)
        assert "error" not in result

    def test_register_custom_tool(self):
        class MockTool(GitStatusTool):
            def name(self) -> str:
                return "mock"

        self.orc.register(MockTool())
        assert "mock" in self.orc.list_tools()
