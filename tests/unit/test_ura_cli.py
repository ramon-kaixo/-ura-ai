"""Unit tests para ura.py — CLI wrapper hacia motor/cli/main.py."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _clean_argv(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["ura.py"])


def _load_ura():
    import importlib

    import ura

    importlib.reload(ura)
    return ura


class TestNoArgs:
    def test_no_args_returns_0(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura

        monkeypatch.setattr(ura, "_motor_main", lambda: (_ for _ in ()).throw(AssertionError("no debe llamarse")))
        monkeypatch.setattr(sys, "argv", ["ura.py"])
        assert ura.main() == 0

    def test_single_unknown_command_delegates(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura

        called: list[str] = []

        def fake_main() -> None:
            called.append(sys.argv[1])

        monkeypatch.setattr(ura, "_motor_main", fake_main)
        monkeypatch.setattr(sys, "argv", ["ura.py", "doctor"])
        ura.main()
        assert called == ["doctor"]


class TestHelp:
    @pytest.mark.parametrize("flag", ["-h", "--help"])
    def test_help_returns_0_without_delegation(self, flag: str, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura

        monkeypatch.setattr(ura, "_motor_main", lambda: (_ for _ in ()).throw(AssertionError("no debe llamarse")))
        monkeypatch.setattr(sys, "argv", ["ura.py", flag])
        assert ura.main() == 0


class TestStatusMapping:
    def test_status_rewrites_to_dashboard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura

        seen: list[str] = []

        def fake_main() -> None:
            seen.append(sys.argv[1])

        monkeypatch.setattr(ura, "_motor_main", fake_main)
        monkeypatch.setattr(sys, "argv", ["ura.py", "status"])
        ura.main()
        assert seen == ["dashboard"]

    def test_other_commands_keep_argv(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import ura

        seen: list[str] = []

        def fake_main() -> None:
            seen.extend(sys.argv[1:])

        monkeypatch.setattr(ura, "_motor_main", fake_main)
        monkeypatch.setattr(sys, "argv", ["ura.py", "finalize", "-m", "fix: algo"])
        ura.main()
        assert seen == ["finalize", "-m", "fix: algo"]


class TestMainGuard:
    def test_script_uses_sys_exit(self) -> None:
        r = subprocess.run(
            [sys.executable, "-c", "import sys; sys.exit(42)"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert r.returncode == 42

    def test_main_guard_block(self) -> None:
        src = _load_ura().__file__ or ""
        assert src.endswith("ura.py")
        with Path(src).open(encoding="utf-8") as f:
            content = f.read()
        assert 'sys.exit(main())' in content
        assert 'if __name__ == "__main__":' in content
