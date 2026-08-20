"""Tests de cobertura para motor/scanner/collector_hw_vm.py (gate 85%, meta 100)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from motor.scanner import collector_hw_vm


class FakeResult:
    def __init__(self, ok: bool = True, stdout: str = "") -> None:
        self.ok = ok
        self.stdout = stdout


class TestEscaneoHwVm:
    @patch("motor.scanner.collector_hw_vm._executor")
    def test_estructura(self, executor: MagicMock) -> None:
        with patch.object(collector_hw_vm, "_dmesg_errors", return_value=["err"]), \
             patch.object(collector_hw_vm, "_io_stats", return_value={"reads": 1}), \
             patch.object(collector_hw_vm, "_virtio_check", return_value=True), \
             patch.object(collector_hw_vm, "_journal_integrity", return_value=2):
            r = collector_hw_vm.escanear_hw_vm()
        assert r["ok"] is True
        assert r["tipo"] == "vm"
        assert r["dmesg_errors"] == ["err"]
        assert r["io_stats"] == {"reads": 1}
        assert r["virtio_ok"] is True
        assert r["journal_corrupt"] == 2


class TestFunciones:
    @patch("motor.scanner.collector_hw_vm._executor")
    def test_dmesg_filtra_usb(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="err1\nusb x\n\nerr2\nerr3\nerr4\nerr5\nerr6")
        assert collector_hw_vm._dmesg_errors() == ["err2", "err3", "err4", "err5", "err6"]

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_dmesg_error(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no dmesg")
        assert collector_hw_vm._dmesg_errors() == []

    @patch("builtins.open", new_callable=MagicMock)
    def test_io_stats_lee_sda(self, mock_open: MagicMock) -> None:
        mock_open.return_value.__enter__.return_value = iter([
            " 8 0 sda 10 20 30 40 50 60 70 80 90 100 110 120",
        ])
        mock_open.return_value.__exit__.return_value = False
        stats = collector_hw_vm._io_stats()
        assert stats == {"reads": 10, "writes": 50, "time_io_ms": 100}

    @patch("builtins.open", new_callable=MagicMock)
    def test_io_stats_sin_sda(self, mock_open: MagicMock) -> None:
        mock_open.return_value.__enter__.return_value = iter([
            " 8 0 nvme0n1 1 2 3 4 5 6 7 8 9 10 11 12",
        ])
        mock_open.return_value.__exit__.return_value = False
        assert collector_hw_vm._io_stats() == {}

    @patch("builtins.open", new_callable=MagicMock)
    def test_io_stats_error(self, mock_open: MagicMock) -> None:
        with patch("builtins.open", side_effect=OSError("no /proc")):
            assert collector_hw_vm._io_stats() == {}

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_virtio_check_true(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="virtio_pci 24576 0")
        assert collector_hw_vm._virtio_check() is True

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_virtio_check_false(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="no modules")
        assert collector_hw_vm._virtio_check() is False

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_virtio_error(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no lsmod")
        assert collector_hw_vm._virtio_check() is False

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_journal_integrity_passes(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="PASS 1\nPASS 2")
        assert collector_hw_vm._journal_integrity() == 2

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_journal_integrity_sin_pass(self, executor: MagicMock) -> None:
        executor.run.return_value = FakeResult(ok=True, stdout="no data")
        assert collector_hw_vm._journal_integrity() == 0

    @patch("motor.scanner.collector_hw_vm._executor")
    def test_journal_error(self, executor: MagicMock) -> None:
        executor.run.side_effect = RuntimeError("no journalctl")
        assert collector_hw_vm._journal_integrity() == 0
