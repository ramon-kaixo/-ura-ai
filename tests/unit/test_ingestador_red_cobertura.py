"""Tests de cobertura para core/ingestador_red.py (ramas de main() y guard __main__).

Complementa test_ingestador_red.py cubriendo las líneas restantes:
  - 211: rama `if result.get("output")` en --distribuir sin --json
  - 217: rama `if args.json` en --status
  - 225: guard `if __name__ == "__main__"` ejecutado via runpy (sin red real,
    subprocess.run mockeado para que tailscale_ssh no llegue a lanzar SSH).
"""

from __future__ import annotations

import runpy
import sys
from types import SimpleNamespace
from unittest import mock

import pytest

import core.ingestador_red as ir


class TestMainBranches:
    def test_distribuir_ok_con_output(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--distribuir", "ping"])
        monkeypatch.setattr(
            ir,
            "distribuir_tarea",
            mock.Mock(return_value={"ok": True, "output": "salida"}),
        )
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 0

    def test_distribuir_fail_con_output(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--distribuir", "ping"])
        monkeypatch.setattr(
            ir,
            "distribuir_tarea",
            mock.Mock(return_value={"ok": False, "output": "", "error": "boom"}),
        )
        with pytest.raises(SystemExit) as e:
            ir.main()
        assert e.value.code == 1

    def test_status_json(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--status", "--json"])
        monkeypatch.setattr(
            ir,
            "estado_dispositivos",
            mock.Mock(return_value={"dispositivos": {"a": {"online": True, "ip_cable": "1", "ip_tailscale": "2"}}}),
        )
        ir.main()

    def test_status_con_offline(self, monkeypatch) -> None:
        monkeypatch.setattr("sys.argv", ["ingestador_red.py", "--status"])
        monkeypatch.setattr(
            ir,
            "estado_dispositivos",
            mock.Mock(
                return_value={
                    "dispositivos": {
                        "a": {"online": True, "ip_cable": "1", "ip_tailscale": "2"},
                        "b": {"online": False, "ip_cable": "3", "ip_tailscale": "4"},
                    }
                }
            ),
        )
        ir.main()


class TestMainGuard:
    """Cubre el guard `if __name__ == "__main__"` sin red real.

    runpy ejecuta el script como __main__; subprocess.run va mockeado para
    que tailscale_ssh (si se alcanza) nunca lance SSH de verdad.
    """

    @staticmethod
    def _run_script(argv: list[str], monkeypatch) -> None:
        monkeypatch.setattr(sys, "argv", argv)
        monkeypatch.setattr(
            ir.subprocess,
            "run",
            mock.Mock(return_value=SimpleNamespace(returncode=0, stdout="ok", stderr="")),
        )
        runpy.run_path(str(ir.URA / "core" / "ingestador_red.py"), run_name="__main__")

    def test_guard_distribuir_json(self, monkeypatch) -> None:
        with pytest.raises(SystemExit) as e:
            self._run_script(["ingestador_red.py", "--distribuir", "ping", "--json"], monkeypatch)
        assert e.value.code == 0

    def test_guard_status(self, monkeypatch) -> None:
        self._run_script(["ingestador_red.py", "--status", "--json"], monkeypatch)

    def test_guard_enviar(self, monkeypatch) -> None:
        with pytest.raises(SystemExit) as e:
            self._run_script(["ingestador_red.py", "--enviar", "backup", "gx10-64c3"], monkeypatch)
        assert e.value.code == 0
