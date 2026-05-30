#!/usr/bin/env python3
"""Tests for core/ura_sandbox_bridge.py."""

from __future__ import annotations

import pytest

from core.ura_sandbox_bridge import (
    SandboxBridge,
    SandboxConfig,
    get_sandbox,
    reset_sandbox,
)


def test_default_mode_is_passthrough(monkeypatch):
    monkeypatch.delenv("URA_SANDBOX_MODE", raising=False)
    cfg = SandboxConfig.from_env()
    assert cfg.mode == "passthrough"


def test_invalid_mode_falls_back_to_passthrough(monkeypatch):
    monkeypatch.setenv("URA_SANDBOX_MODE", "invent_mode")
    cfg = SandboxConfig.from_env()
    assert cfg.mode == "passthrough"


def test_ssh_mode_loads_env_vars(monkeypatch):
    monkeypatch.setenv("URA_SANDBOX_MODE", "ssh")
    monkeypatch.setenv("URA_SANDBOX_SSH_HOST", "user@vm")
    monkeypatch.setenv("URA_SANDBOX_SSH_KEY", "/tmp/k")
    cfg = SandboxConfig.from_env()
    assert cfg.mode == "ssh"
    assert cfg.ssh_host == "user@vm"
    assert cfg.ssh_key == "/tmp/k"


def test_lima_mode_loads_env_vars(monkeypatch):
    monkeypatch.setenv("URA_SANDBOX_MODE", "lima")
    monkeypatch.setenv("URA_SANDBOX_LIMA_NAME", "ura-vm")
    cfg = SandboxConfig.from_env()
    assert cfg.mode == "lima"
    assert cfg.lima_name == "ura-vm"


def test_is_isolated_only_for_ssh_or_lima():
    assert SandboxBridge(SandboxConfig(mode="passthrough")).is_isolated is False
    assert SandboxBridge(SandboxConfig(mode="ssh", ssh_host="x")).is_isolated is True
    assert SandboxBridge(SandboxConfig(mode="lima", lima_name="x")).is_isolated is True


def test_info_returns_full_config():
    bridge = SandboxBridge(SandboxConfig(mode="passthrough"))
    info = bridge.info()
    assert info["mode"] == "passthrough"
    assert info["is_isolated"] is False
    assert "config" in info


@pytest.mark.asyncio
async def test_run_command_passthrough_executes_locally():
    bridge = SandboxBridge(SandboxConfig(mode="passthrough"))
    out = await bridge.run_command(["echo", "hola sandbox"], timeout_s=5)
    assert "hola sandbox" in out


@pytest.mark.asyncio
async def test_run_command_invalid_returns_empty():
    bridge = SandboxBridge(SandboxConfig(mode="passthrough"))
    out = await bridge.run_command(["__cmd_que_no_existe_xyz__"], timeout_s=2)
    assert out == ""


def test_singleton_reset(monkeypatch):
    monkeypatch.delenv("URA_SANDBOX_MODE", raising=False)
    reset_sandbox()
    a = get_sandbox()
    b = get_sandbox()
    assert a is b
    reset_sandbox()
    c = get_sandbox()
    assert c is not a
