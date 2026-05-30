"""Tests for core: n8n_builder, n8n_validator, tool_manager, tool_registry, storage, messaging, telegram_bridge, docker_bridge, browser_agent, websocket, self_healing, security_policy, terminal_gateway."""

import logging


logging.disable(logging.CRITICAL)


class TestN8nWorkflowBuilder:
    def test_imports(self):
        from core.n8n_workflow_builder import construir_workflow

        assert callable(construir_workflow)


class TestN8nWorkflowValidator:
    def test_imports(self):
        from core.n8n_workflow_validator import validar_workflow

        assert callable(validar_workflow)


class TestToolManager:
    def test_imports(self):
        from core.tool_manager import ToolManager

        assert ToolManager is not None


class TestToolRegistry:
    def test_imports(self):
        from core.tool_registry import TOOL_REGISTRY

        assert TOOL_REGISTRY is not None


class TestStorageManager:
    def test_imports(self):
        from core.storage_manager import StorageManager

        assert StorageManager is not None


class TestMessagingTools:
    def test_imports(self):
        from core.messaging_tools import MessagingTools

        assert MessagingTools is not None


class TestTelegramSecurityBridge:
    def test_imports(self):
        from core.telegram_security_bridge import TelegramSecurityBridge

        assert TelegramSecurityBridge is not None


class TestDockerBridge:
    def test_imports(self):
        from core.docker_bridge import DockerBridge

        assert DockerBridge is not None


class TestTerminalGateway:
    def test_imports(self):
        from core.terminal_gateway import TerminalGateway

        assert TerminalGateway is not None
