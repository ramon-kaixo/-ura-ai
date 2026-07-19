"""Tests for motor/platform/registry.py — ProtocolRegistry.

Covers: register_message_type, get_schema_version, supports_message_type,
duplicate registration, message_types property, thread safety.
"""

from __future__ import annotations

import threading

from motor.platform import ProtocolRegistry


def test_register_basic() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("TestRequest", "1.0")
    assert reg.get_schema_version("TestRequest") == "1.0"
    assert reg.supports_message_type("TestRequest") is True


def test_get_schema_version() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("TestRequest", "1.0")
    assert reg.get_schema_version("TestRequest") == "1.0"


def test_get_schema_version_missing() -> None:
    reg = ProtocolRegistry()
    assert reg.get_schema_version("Unknown") is None


def test_supports_message_type() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("TestRequest", "1.0")
    assert reg.supports_message_type("TestRequest") is True
    assert reg.supports_message_type("Unknown") is False


def test_duplicate_registration_overwrites_schema_version() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("TestRequest", "1.0")
    reg.register_message_type("TestRequest", "2.0")
    assert reg.get_schema_version("TestRequest") == "2.0"
    assert reg.supports_message_type("TestRequest") is True


def test_duplicate_registration_still_registered() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("TestRequest", "1.0")
    reg.register_message_type("TestRequest", "2.0")
    assert reg.supports_message_type("TestRequest") is True


def test_message_types_property() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("Alpha", "1.0")
    reg.register_message_type("Beta", "2.0")
    assert reg.message_types == {"Alpha": "1.0", "Beta": "2.0"}


def test_message_types_property_is_copy() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("Original", "1.0")
    result = reg.message_types
    result["Tampered"] = "99.0"
    assert "Tampered" not in reg.message_types


def test_list_types_empty() -> None:
    reg = ProtocolRegistry()
    assert reg.message_types == {}


def test_multiple_types_same_version() -> None:
    reg = ProtocolRegistry()
    reg.register_message_type("A", "1.0")
    reg.register_message_type("B", "1.0")
    assert reg.get_schema_version("A") == "1.0"
    assert reg.get_schema_version("B") == "1.0"


def test_thread_safety() -> None:
    reg = ProtocolRegistry()
    n = 100
    errors: list[Exception] = []

    def worker(start: int) -> None:
        for i in range(start, start + n):
            try:
                typename = f"Msg{i}"
                ver = f"{i % 10}.0"
                reg.register_message_type(typename, ver)
                _ = reg.supports_message_type(typename)
                _ = reg.get_schema_version(typename)
                _ = reg.message_types
            except Exception as exc:
                errors.append(exc)

    threads = [threading.Thread(target=worker, args=(i * n,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=5)

    assert not errors
    assert len(reg.message_types) == 4 * n


def test_register_protocol_version_and_check() -> None:
    reg = ProtocolRegistry()
    reg.register_protocol_version("2.0")
    assert reg.supports_protocol("2.0") is True
    assert reg.supports_protocol("1.0") is False


def test_register_capability_and_check() -> None:
    reg = ProtocolRegistry()
    reg.register_capability("streaming")
    assert reg.supports_capability("streaming") is True
    assert reg.supports_capability("batched") is False


def test_protocol_versions_property() -> None:
    reg = ProtocolRegistry()
    reg.register_protocol_version("1.0")
    reg.register_protocol_version("2.0")
    assert reg.protocol_versions == {"1.0", "2.0"}


def test_protocol_versions_property_is_copy() -> None:
    reg = ProtocolRegistry()
    reg.register_protocol_version("1.0")
    result = reg.protocol_versions
    result.add("99.0")
    assert "99.0" not in reg.protocol_versions
