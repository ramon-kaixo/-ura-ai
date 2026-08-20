"""Cobertura 100x100 de motor/guard (verifier + preflight). TASK-20260820-006."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from motor.core.config import UraConfig
from motor.core.executor import ProcessResult
from motor.guard import preflight, verifier
from motor.guard.preflight import ejecutar_preflight
from motor.guard.verifier import ejecutar_verificacion


@dataclass
class _ExecResult:
    ok: bool
    stdout: str = ""
    error: str = ""
    returncode: int = 0


class _FakeExecutor:
    def __init__(self, results: list[_ExecResult] | None = None) -> None:
        self.results = list(results or [])
        self.calls: list[list[str]] = []
        self.raise_exc: Exception | None = None

    def run(self, cmd: list[str], timeout: int = 30) -> ProcessResult:
        self.calls.append(cmd)
        if self.raise_exc:
            raise self.raise_exc
        r = self.results.pop(0) if self.results else _ExecResult(ok=True, stdout="")
        return ProcessResult(ok=r.ok, cmd=cmd, returncode=r.returncode, stdout=r.stdout, error=r.error)


# ── verifier ─────────────────────────────────────────────────


def test_verificacion_sin_cambios_skip(monkeypatch: pytest.MonkeyPatch) -> None:
    def _no_sleep(s: float) -> None:
        msg = "no debe dormir"
        raise AssertionError(msg)

    monkeypatch.setattr(verifier.time, "sleep", _no_sleep)
    r = ejecutar_verificacion(UraConfig(), hubo_cambios=False)
    assert r.verdict == "no_changes"
    assert r.ok is True


def test_verificacion_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor([_ExecResult(ok=True, stdout='{"choices": [{"message": {"content": "hola"}}]}')])
    monkeypatch.setattr(verifier, "_executor", fx)
    monkeypatch.setattr(verifier.time, "sleep", lambda s: None)
    r = ejecutar_verificacion(UraConfig(), hubo_cambios=True)
    assert r.ok is True
    assert r.verdict == "ok"
    assert r.test_response == "hola"
    assert fx.calls[0][0] == "curl"


def test_verificacion_fail_sin_auto_revert(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor([_ExecResult(ok=False, stdout="")])
    monkeypatch.setattr(verifier, "_executor", fx)
    monkeypatch.setattr(verifier.time, "sleep", lambda s: None)
    cfg = UraConfig(auto_verify=False)
    r = ejecutar_verificacion(cfg, hubo_cambios=True)
    assert r.ok is False
    assert r.verdict == "fail"
    assert r.revertido is False


def test_verificacion_fail_con_auto_revert(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor([_ExecResult(ok=False, stdout=""), _ExecResult(ok=True, stdout="")])
    monkeypatch.setattr(verifier, "_executor", fx)
    monkeypatch.setattr(verifier.time, "sleep", lambda s: None)
    cfg = UraConfig(auto_verify=True)
    r = ejecutar_verificacion(cfg, hubo_cambios=True)
    assert r.ok is False
    assert r.verdict == "reverted"
    assert r.revertido is True
    assert fx.calls[1][0] == "systemctl"


def test_test_ollama_respuesta_vacia_choices() -> None:
    fx = _FakeExecutor([_ExecResult(ok=True, stdout='{"choices": []}')])
    verifier._executor = fx
    assert verifier._test_ollama() == "ok"


def test_test_ollama_json_invalido(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="no-json")])
    monkeypatch.setattr(verifier, "_executor", fx)
    assert verifier._test_ollama() == ""


def test_test_ollama_json_sin_choices() -> None:
    fx = _FakeExecutor([_ExecResult(ok=True, stdout='{"otro": 1}')])
    verifier._executor = fx
    assert verifier._test_ollama() == ""


def test_test_ollama_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor()
    fx.raise_exc = RuntimeError("curl no existe")
    monkeypatch.setattr(verifier, "_executor", fx)
    assert verifier._test_ollama() == ""


def test_revertir_cambios_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="")])
    monkeypatch.setattr(verifier, "_executor", fx)
    verifier._revertir_cambios()
    assert fx.calls[0][0] == "systemctl"


def test_revertir_cambios_excepcion(monkeypatch: pytest.MonkeyPatch) -> None:
    fx = _FakeExecutor()
    fx.raise_exc = RuntimeError("denegado")
    monkeypatch.setattr(verifier, "_executor", fx)
    verifier._revertir_cambios()  # no debe lanzar


def test_test_ollama_content_truncado_100() -> None:
    largo = "x" * 200
    fx = _FakeExecutor([_ExecResult(ok=True, stdout=json.dumps({"choices": [{"message": {"content": largo}}]}))])
    verifier._executor = fx
    assert verifier._test_ollama() == "x" * 100


# ── preflight ────────────────────────────────────────────────


def test_preflight_ok_sin_duplicadas(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [])
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="pid1 proc1\npid2 proc2\n")])
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    assert r.ok is True
    assert r.bloqueado is False
    assert r.snapshot_path != ""
    assert (tmp_path / "snapshots").exists()
    snap = json.loads(Path(r.snapshot_path).read_text())
    assert snap["procesos"][0] == "pid1 proc1"


def test_preflight_bloqueo_por_duplicadas(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta1 = str(tmp_path / "opencode.json")
    ruta2 = str(tmp_path / "opencode.jsonc")
    Path(ruta1).write_text("{}")
    Path(ruta2).write_text("{}")
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [ruta1, ruta2])
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="")])
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    assert r.ok is False
    assert r.bloqueado is True
    assert "duplicadas" in r.razon
    assert r.configs_duplicadas == [ruta1, ruta2]


def test_preflight_snapshot_configs_hashes(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    ruta1 = str(tmp_path / "opencode.json")
    Path(ruta1).write_text('{"a": 1}')
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [ruta1, str(tmp_path / "no-existe.json")])
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="")])
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    snap = json.loads(Path(r.snapshot_path).read_text())
    assert ruta1 in snap["configs"]
    assert len(snap["configs"][ruta1]["hash"]) == 16
    assert str(tmp_path / "no-existe.json") not in snap["configs"]


def test_preflight_procesos_excepcion(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [])
    fx = _FakeExecutor()
    fx.raise_exc = RuntimeError("ps falló")
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    snap = json.loads(Path(r.snapshot_path).read_text())
    assert snap["procesos"] == []


def test_preflight_procesos_lineas_vacias_filtradas(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [])
    fx = _FakeExecutor([_ExecResult(ok=True, stdout="\npid1 proc1\n\npid2 proc2\n\n")])
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    snap = json.loads(Path(r.snapshot_path).read_text())
    assert snap["procesos"] == ["pid1 proc1", "pid2 proc2"]


def test_preflight_procesos_limitado_a_30(tmp_path: object, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(preflight, "RUTAS_CONFIG_OPENCODE", [])
    lineas = "\n".join(f"p{i} proc{i}" for i in range(40))
    fx = _FakeExecutor([_ExecResult(ok=True, stdout=lineas)])
    monkeypatch.setattr(preflight, "_executor", fx)
    cfg = UraConfig(data_dir=str(tmp_path))
    r = ejecutar_preflight(cfg)
    snap = json.loads(Path(r.snapshot_path).read_text())
    assert len(snap["procesos"]) == 30


def test_preflight_snapshot_path_timestamp() -> None:
    import re

    path = "/tmp/preflight_20260820_123456.json"
    assert re.match(r"preflight_\d{8}_\d{6}\.json", path.rsplit("/", maxsplit=1)[-1])
