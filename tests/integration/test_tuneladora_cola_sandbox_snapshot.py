"""Tests para llm_fallback, pending_queue, sandbox y snapshot de la tuneladora."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import requests

from scripts.pro.tuneladora.config import Configuration
from scripts.pro.tuneladora.pipeline.llm_fallback import LLMFallback
from scripts.pro.tuneladora.pipeline.pending_queue import PendingQueue
from scripts.pro.tuneladora.pipeline.sandbox import preexec_fn, set_sandbox_limits
from scripts.pro.tuneladora.snapshot import SnapshotService


def _cfg(tmp_path: Path) -> Configuration:
    cfg = Configuration()
    cfg.tuneladora_dir = tmp_path / "tuneladora"
    cfg.tuneladora_dir.mkdir(parents=True, exist_ok=True)
    cfg.ollama_url = "http://localhost:11434"
    cfg.timeout_llm = 30
    cfg.llm_fallback_model = "qwen"
    cfg.llm_retries = 2
    return cfg


class TestPendingQueue:
    def _queue(self, tmp_path: Path) -> PendingQueue:
        return PendingQueue(tmp_path / "tuneladora.db")

    def test_add_y_list(self, tmp_path: Path) -> None:
        q = self._queue(tmp_path)
        q.add(archivo="a.py", herramienta="ruff", severidad="high", error_raw="E501", bloque="static")
        items = q.list_pending()
        assert len(items) == 1
        assert items[0]["archivo"] == "a.py"
        assert items[0]["estado"] == "pendiente"

    def test_list_filtro_severidad(self, tmp_path: Path) -> None:
        q = self._queue(tmp_path)
        q.add(archivo="a", herramienta="r", severidad="high", error_raw="x")
        q.add(archivo="b", herramienta="r", severidad="low", error_raw="y")
        assert len(q.list_pending(severidad="high")) == 1

    def test_resolve(self, tmp_path: Path) -> None:
        q = self._queue(tmp_path)
        fix_id = q.add(archivo="a", herramienta="r", severidad="high", error_raw="x")
        q.resolve(fix_id, "hecho")
        assert q.list_pending() == []

    def test_record_run_y_stats(self, tmp_path: Path) -> None:
        q = self._queue(tmp_path)
        q.record_run(mode="check", verdict="OK", seconds=1.5, n_files=2)
        q.record_run(mode="check", verdict="FAIL", seconds=0.5)
        stats = q.stats()
        assert stats["total_runs"] == 2
        assert stats["ok_runs"] == 1
        assert stats["fail_runs"] == 1

    def test_init_falla_modo_degradado(self, tmp_path: Path) -> None:
        with mock.patch.object(PendingQueue, "_ensure_tables", side_effect=sqlite3.Error("boom")):
            q = PendingQueue(tmp_path / "db.sqlite")
        assert q.ok is False
        assert q.add(archivo="a", herramienta="r", severidad="x", error_raw="y") == 0
        assert q.list_pending() == []
        assert q.stats()["pending_fixes"] == 0


class TestLLMFallback:
    def test_analyze_ok(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        q = PendingQueue(tmp_path / "q.db")
        lf = LLMFallback(cfg, q)
        archivo = tmp_path / "a.py"
        archivo.write_text("def x():\n    pass\n")
        resp = SimpleNamespace(
            status_code=200,
            raise_for_status=lambda: None,
            json=lambda: {"response": "--- a.py\n+++ b.py\n"},
        )
        with mock.patch("requests.post", return_value=resp) as m_post:
            patch = lf.analyze("E501", str(archivo), "ruff")
        assert patch and patch.startswith("---")
        assert m_post.call_args[1]["json"]["options"]["num_predict"] > 0
        patches = list((cfg.tuneladora_dir / "patches").glob("*.diff"))
        assert len(patches) == 1

    def test_analyze_patch_vacio(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        lf = LLMFallback(cfg, PendingQueue(tmp_path / "q.db"))
        archivo = tmp_path / "a.py"
        archivo.write_text("x")
        resp = SimpleNamespace(status_code=200, raise_for_status=lambda: None, json=lambda: {"response": "  "})
        with mock.patch("requests.post", return_value=resp):
            assert lf.analyze("err", str(archivo)) is None

    def test_analyze_ollama_agotado_encola(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        q = PendingQueue(tmp_path / "q.db")
        lf = LLMFallback(cfg, q)
        archivo = tmp_path / "a.py"
        archivo.write_text("x")
        with mock.patch("requests.post", side_effect=requests.RequestException("conn")):
            assert lf.analyze("err", str(archivo)) is None
        conn = sqlite3.connect(tmp_path / "q.db")
        row = conn.execute("SELECT estado, bloque FROM pending_fixes").fetchone()
        conn.close()
        assert row == ("imposible", "llm_fallback")

    def test_get_code_context_archivo_inexistente(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        lf = LLMFallback(cfg, PendingQueue(tmp_path / "q.db"))
        assert lf._get_code_context("/no/existe.py") == ""

    def test_analyze_excepcion_general(self, tmp_path: Path) -> None:
        cfg = _cfg(tmp_path)
        lf = LLMFallback(cfg, PendingQueue(tmp_path / "q.db"))
        with mock.patch.object(lf, "_get_code_context", side_effect=RuntimeError("boom")):
            assert lf.analyze("err", "x.py") is None


class TestSandbox:
    def test_set_limits(self) -> None:
        import resource

        with mock.patch("resource.setrlimit") as m_set:
            set_sandbox_limits(cpu_sec=10, max_mem=1024 * 1024)
        assert m_set.call_count == 2
        assert m_set.call_args_list[0][0][0] == resource.RLIMIT_CPU
        assert m_set.call_args_list[1][0][0] == resource.RLIMIT_AS

    def test_preexec(self) -> None:
        with mock.patch("scripts.pro.tuneladora.pipeline.sandbox.set_sandbox_limits") as m_set:
            preexec_fn()
        m_set.assert_called_once()


class TestSnapshotService:
    @staticmethod
    def _sistema_map(tmp_path: Path) -> None:
        (tmp_path / "sistema_map.json").write_text(
            json.dumps(
                {
                    "dependency_graph": {
                        "a.py": {
                            "pipeline_state": "ACTIVO",
                            "checksum_blake2b_8": "abc123",
                            "allocation_bytes": 42,
                            "posix_timestamps": {"st_mtime": 1700000000},
                        },
                        "b.py": {"pipeline_state": "ESPEJO", "checksum_blake2b_8": "zzz"},
                        "c.py": {"pipeline_state": "ZOMBIE", "checksum_blake2b_8": "yyy"},
                    }
                },
            ),
            encoding="utf-8",
        )

    def test_save_ok(self, tmp_path: Path) -> None:
        log_calls: list[str] = []
        self._sistema_map(tmp_path)
        svc = SnapshotService(tmp_path, log_fn=log_calls.append)
        out = svc.save("ciclo")
        assert out == tmp_path / "delta_snapshots" / "ciclo.json"
        assert out is not None and out.exists()
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["label"] == "ciclo"
        assert set(payload["files"]) == {"a.py"}
        assert payload["files"]["a.py"]["blake2b"] == "abc123"
        assert any("guardado" in l for l in log_calls)

    def test_save_sin_mapa(self, tmp_path: Path) -> None:
        log_calls: list[str] = []
        svc = SnapshotService(tmp_path, log_fn=log_calls.append)
        out = svc.save("ciclo")
        assert out is not None and out.exists()
        assert json.loads(out.read_text(encoding="utf-8"))["files"] == {}

    def test_save_falla(self, tmp_path: Path) -> None:
        log_calls: list[str] = []
        (tmp_path / "sistema_map.json").write_text("{corrupto", encoding="utf-8")
        svc = SnapshotService(tmp_path, log_fn=log_calls.append)
        assert svc.save("ciclo") is None
        assert any("falló" in l for l in log_calls)

    def test_exists(self, tmp_path: Path) -> None:
        svc = SnapshotService(tmp_path)
        assert svc.exists() is False
        d = tmp_path / "delta_snapshots"
        d.mkdir()
        (d / "ultimo_ciclo.json").write_text("{}")
        assert svc.exists() is True

    def test_clean(self, tmp_path: Path) -> None:
        d = tmp_path / "delta_snapshots"
        d.mkdir()
        (d / "x.json").write_text("{}")
        log_calls: list[str] = []
        svc = SnapshotService(tmp_path, log_fn=log_calls.append)
        svc.clean()
        assert not d.exists()
        assert log_calls
