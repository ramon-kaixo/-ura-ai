"""Tests para core/sandbox/docker_orchestrator.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "scripts" / "pro"))

from core.sandbox.docker_orchestrator import DockerOrchestrator, ResultadoSandbox  # noqa: E402


class TestResultadoSandbox:
    def test_resumen_ok(self) -> None:
        r = ResultadoSandbox(True, True, 3, 0, [], "out", "err", 1.5, 10.0, None)
        txt = r.resumen()
        assert "[Sandbox] OK" in txt
        assert "Tests: 3 OK, 0 FAIL" in txt

    def test_resumen_fail_con_fallos(self) -> None:
        r = ResultadoSandbox(False, True, 1, 2, ["test_a"], "out", "err", 1.0, 5.0, "algo fallo")
        txt = r.resumen()
        assert "[Sandbox] FAIL" in txt
        assert "test_a" in txt
        assert "ERROR: algo fallo" in txt

    def test_ts_default(self) -> None:
        r = ResultadoSandbox(True, True, 0, 0, [], "", "", 0, 0, None)
        assert "T" in r.ts


class TestDockerOrchestrator:
    @pytest.mark.asyncio
    async def test_validar_docker_no_disponible(self, monkeypatch) -> None:
        monkeypatch.setattr(DockerOrchestrator, "_docker", mock.Mock(return_value=False))
        orq = DockerOrchestrator(td=Path("/tmp/noexiste_tests"))
        r = await orq.validar("codigo", "skill1")
        assert r.ok is False
        assert r.error == "Docker no disponible"
        assert r.ejecuto is False

    @pytest.mark.asyncio
    async def test_validar_flujo_completo_ok(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(DockerOrchestrator, "_docker", mock.Mock(return_value=True))
        orq = DockerOrchestrator(td=tmp_path / "tests_src")

        proc = mock.Mock()
        proc.returncode = 0
        proc.communicate = mock.AsyncMock(return_value=(b"", b""))
        build = mock.Mock()
        build.communicate = mock.AsyncMock(return_value=(b"", b""))
        build.returncode = 0
        run = mock.Mock()
        run.returncode = 0
        # "fallos" (no "fallidos") es la clave que chequea el codigo — typo real
        datos = {"ejecuto": True, "pasados": 2, "fallidos": 0, "fallos": 0, "fallos_nombres": [], "error": None}
        run.communicate = mock.AsyncMock(return_value=(json.dumps(datos).encode(), b""))

        def fake_exec(*args, **kwargs):
            if args[0] == "docker" and args[1] == "build":
                return build
            return run

        monkeypatch.setattr(asyncio_module(), "create_subprocess_exec", mock.AsyncMock(side_effect=fake_exec))
        r = await orq.validar("codigo", "skill1")
        assert r.ok is True
        assert r.pasados == 2
        assert r.fallidos == 0
        # rmi al final
        subprocess_run = mock.Mock()
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", subprocess_run)
        assert r.ejecuto is True

    @pytest.mark.asyncio
    async def test_validar_build_fail(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(DockerOrchestrator, "_docker", mock.Mock(return_value=True))
        orq = DockerOrchestrator(td=tmp_path / "tests_src")

        build = mock.Mock()
        build.communicate = mock.AsyncMock(return_value=(b"", b"error de build"))
        build.returncode = 1

        def fake_exec(*args, **kwargs):
            return build

        monkeypatch.setattr(asyncio_module(), "create_subprocess_exec", mock.AsyncMock(side_effect=fake_exec))
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock())
        r = await orq.validar("codigo", "skill1")
        assert r.ok is False
        assert r.error == "build fail"
        assert "error de build" in r.stderr

    @pytest.mark.asyncio
    async def test_validar_timeout(self, monkeypatch, tmp_path) -> None:
        monkeypatch.setattr(DockerOrchestrator, "_docker", mock.Mock(return_value=True))
        orq = DockerOrchestrator(td=tmp_path / "tests_src")

        build = mock.Mock()
        build.communicate = mock.AsyncMock(return_value=(b"", b""))
        build.returncode = 0
        run = mock.Mock()
        run.communicate = mock.AsyncMock(side_effect=TimeoutError())
        run.kill = mock.Mock()

        calls = {"n": 0}

        def fake_exec(*args, **kwargs):
            if args[0] == "docker" and args[1] == "build":
                return build
            return run

        monkeypatch.setattr(asyncio_module(), "create_subprocess_exec", mock.AsyncMock(side_effect=fake_exec))
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock())
        r = await orq.validar("codigo", "skill1")
        assert r.ok is False
        assert r.error == "timeout"
        run.kill.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_sin_tests_dir_crea_default(self, monkeypatch, tmp_path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        orq = DockerOrchestrator(td=tmp_path / "noexiste")

        build = mock.Mock()
        build.communicate = mock.AsyncMock(return_value=(b"", b""))
        build.returncode = 0
        run = mock.Mock()
        run.communicate = mock.AsyncMock(return_value=(b"", b""))
        run.returncode = 0

        def fake_exec(*args, **kwargs):
            return build if args[1] == "build" else run

        monkeypatch.setattr(asyncio_module(), "create_subprocess_exec", mock.AsyncMock(side_effect=fake_exec))
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock())
        await orq._run(d, "cod", "skill1")
        assert (d / "tests" / "ts.py").exists()
        assert (d / "Dockerfile").exists()
        assert (d / "rv.py").exists()

    @pytest.mark.asyncio
    async def test_run_parsea_resultado_con_fallos(self, monkeypatch, tmp_path) -> None:
        d = tmp_path / "d"
        d.mkdir()
        orq = DockerOrchestrator(td=tmp_path / "noexiste")
        datos = {"ejecuto": True, "pasados": 1, "fallidos": 2, "fallos_nombres": ["a", "b"], "error": None}

        build = mock.Mock()
        build.communicate = mock.AsyncMock(return_value=(b"", b""))
        build.returncode = 0
        run = mock.Mock()
        run.communicate = mock.AsyncMock(return_value=(json.dumps(datos).encode(), b"linea error"))
        run.returncode = 1

        def fake_exec(*args, **kwargs):
            return build if args[1] == "build" else run

        monkeypatch.setattr(asyncio_module(), "create_subprocess_exec", mock.AsyncMock(side_effect=fake_exec))
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock())
        r = await orq._run(d, "cod", "skill1")
        assert r.ok is False
        assert r.fallidos == 2
        assert r.fallos == ["a", "b"]


class TestStatic:
    def test_df_genera_dockerfile(self) -> None:
        df = DockerOrchestrator._df("cod", "skill1")
        assert "python:3.12-slim" in df
        assert "pytest" in df
        assert "COPY skills/" in df

    def test_rv_contiene_runner(self) -> None:
        rv = DockerOrchestrator._rv("skill1")
        assert "skill1" in rv
        assert "pytest" in rv
        assert "json" in rv

    def test_docker_info_ok(self, monkeypatch) -> None:
        res = SimpleNamespace(returncode=0)
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock(return_value=res))
        assert DockerOrchestrator._docker() is True

    def test_docker_info_error(self, monkeypatch) -> None:
        monkeypatch.setattr("core.sandbox.docker_orchestrator.subprocess.run", mock.Mock(side_effect=FileNotFoundError("no docker")))
        assert DockerOrchestrator._docker() is False


def asyncio_module():
    import asyncio

    return asyncio
