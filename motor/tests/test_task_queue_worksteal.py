"""Tests del pool de trabajo (work-stealing) y pausa/reanudación de tareas.

Cubre la lógica nueva de TaskQueue (claim_next, pause/resume, park_in_progress,
release_pending, release_all_paused, list_resumable) y de WorkStealer
(acquire/release/is_present/rebalance). Usa SQLite en tmp_path, sin red.
"""

from __future__ import annotations

import threading

from motor.orchestration.worksteal import WorkStealer

from motor.orchestration.task_queue import TaskQueue, TaskStatus


def _queue(tmp_path) -> TaskQueue:
    return TaskQueue(db_path=tmp_path / "test_queue.db")


def test_claim_next_own_node_priority(tmp_path):
    q = _queue(tmp_path)
    q.create("t1", node_id="mac")
    q.create("t2", node_id="gx10")

    picked = q.claim_next("worker-gx10", "gx10")
    assert picked is not None
    assert picked.node_id == "gx10"
    assert picked.status == TaskStatus.ASSIGNED.value

    picked_mac = q.claim_next("worker-mac", "mac")
    assert picked_mac is not None
    assert picked_mac.node_id == "mac"


def test_claim_next_steals_when_own_empty(tmp_path):
    q = _queue(tmp_path)
    created = q.create("t-gx10", node_id="gx10")

    # worker-mac sin tareas propias roba la de gx10 (work-stealing por ociosidad)
    picked = q.claim_next("worker-mac", "mac")
    assert picked is not None
    assert picked.id == created.id


def test_claim_next_none_when_empty(tmp_path):
    q = _queue(tmp_path)
    assert q.claim_next("worker-x", "mac") is None


def test_pause_and_resume(tmp_path):
    q = _queue(tmp_path)
    t = q.create("tarea")
    q.claim(t.id, "worker-mac")
    q.start(t.id)
    assert q.get(t.id).status == TaskStatus.IN_PROGRESS.value

    paused = q.pause(t.id, "mac")
    assert paused.status == TaskStatus.PAUSED.value
    # paused no se puede robar ni completar directo
    assert q.claim(t.id, "worker-gx10") is None

    resumed = q.resume(t.id, "mac")
    assert resumed.status == TaskStatus.ASSIGNED.value
    assert resumed.assigned_to == "mac"


def test_list_resumable_only_own_node(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    b = q.create("b")
    q.claim(a.id, "mac")
    q.claim(b.id, "gx10")
    q.start(a.id)
    q.start(b.id)
    q.pause(a.id, "mac")
    q.pause(b.id, "gx10")

    mac = q.list_resumable("mac")
    gx = q.list_resumable("gx10")
    assert [t.id for t in mac] == [a.id]
    assert [t.id for t in gx] == [b.id]


def test_park_in_progress_reserves_to_node(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    q.claim(a.id, "mac")
    q.start(a.id)

    parked = q.park_in_progress("mac")
    assert parked == 1
    assert q.get(a.id).status == TaskStatus.PAUSED.value
    assert q.get(a.id).assigned_to == "mac"
    # otro nodo no la puede reclamar (paused)
    assert q.claim(a.id, "gx10") is None


def test_release_pending_frees_to_common_queue(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    b = q.create("b")
    q.claim(a.id, "mac")
    q.claim(b.id, "gx10")
    q.start(b.id)
    q.pause(b.id, "gx10")  # b "a medio hacer" queda reservada

    released = q.release_pending("mac")
    assert released == 1
    # a volvió a pending común; b quedó paused (no se tocó)
    assert q.get(a.id).status == TaskStatus.PENDING.value
    assert q.get(a.id).assigned_to == ""
    assert q.get(b.id).status == TaskStatus.PAUSED.value


def test_release_all_paused_force(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    q.claim(a.id, "mac")
    q.start(a.id)
    q.pause(a.id, "mac")

    released = q.release_all_paused("mac")
    assert released == 1
    assert q.get(a.id).status == TaskStatus.PENDING.value
    # ahora otro nodo puede robarla
    picked = q.claim_next("worker-gx10", "gx10")
    assert picked is not None
    assert picked.id == a.id


def test_steal_available_ignores_paused(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    b = q.create("b")
    q.claim(a.id, "mac")
    q.start(a.id)
    q.pause(a.id, "mac")  # paused no debe aparecer como "available"

    avail = q.steal_available("gx10", limit=10)
    ids = [t.id for t in avail]
    assert a.id not in ids
    assert b.id in ids


def test_workstealer_acquire_release_presence(tmp_path):
    q = _queue(tmp_path)
    ws = WorkStealer(q, offline_threshold_s=1000.0)
    ws.acquire("mac")
    assert ws.is_present("mac") is True
    ws.release("mac")
    assert ws.is_present("mac") is False


def test_workstealer_release_parks_in_progress(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    q.claim(a.id, "mac")
    q.start(a.id)

    ws = WorkStealer(q, offline_threshold_s=1000.0)
    ws.acquire("mac")
    ws.release("mac")
    # su tarea in_progress quedó paused (reservada)
    assert q.get(a.id).status == TaskStatus.PAUSED.value
    assert q.get(a.id).assigned_to == "mac"


def test_workstealer_rebalance_offline_node(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    b = q.create("b")
    q.claim(a.id, "mac")
    q.claim(b.id, "mac")
    q.start(a.id)
    q.start(b.id)

    ws = WorkStealer(q, offline_threshold_s=-1.0)  # umbral negativo → vence al instante
    ws.acquire("mac")
    # forzar expiración: el último seen queda en el pasado
    ws._node_last_seen["mac"] = 0.0

    counts = ws.rebalance()
    assert counts["parked"] == 2
    assert q.get(a.id).status == TaskStatus.PAUSED.value
    assert q.get(b.id).status == TaskStatus.PAUSED.value


def test_workstealer_rebalance_force_releases_paused(tmp_path):
    q = _queue(tmp_path)
    a = q.create("a")
    q.claim(a.id, "mac")
    q.start(a.id)

    ws = WorkStealer(q, offline_threshold_s=-1.0)
    ws.acquire("mac")
    ws._node_last_seen["mac"] = 0.0

    counts = ws.rebalance(force=True)
    assert counts["parked"] == 1
    assert counts["stolen_released"] == 1
    assert q.get(a.id).status == TaskStatus.PENDING.value


def test_workstealer_steal_available(tmp_path):
    q = _queue(tmp_path)
    q.create("x")
    ws = WorkStealer(q, offline_threshold_s=1000.0)
    assert len(ws.steal_available("gx10", limit=10)) >= 1


def test_workstealer_start_stop_status(tmp_path):
    q = _queue(tmp_path)
    ws = WorkStealer(q, offline_threshold_s=100.0)
    ws.acquire("mac")
    # start ya iniciado no duplica hilo
    ws.start(interval_s=0.05)
    ws.start(interval_s=0.05)
    st = ws.status()
    assert st["running"] is True
    assert st["nodes"].get("mac") is True
    ws.stop()
    st2 = ws.status()
    assert st2["running"] is False


def test_workstealer_rebalance_all_idle(tmp_path):
    q = _queue(tmp_path)
    ws = WorkStealer(q, offline_threshold_s=1000.0)
    ws.acquire("mac")
    ws.acquire("gx10")
    counts = ws.rebalance(force=True)
    assert counts["parked"] == 0
    assert counts["released"] == 0


# ---------------------------------------------------------------------------
# NodeWorker (worker daemon) — con TaskQueue real y que no invoca opencode
# ---------------------------------------------------------------------------

from motor.orchestration.worker import NodeWorker, WorkerError


class _FakeTask:
    """Tarea mínima compatible para el worker."""

    def __init__(self, tid: str, desc: str = "desc", timeout: int = 30) -> None:
        self.id = tid
        self.description = desc
        self.timeout_seconds = timeout


def test_worker_run_once_complete(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(
        node_id="mac",
        agent="worker-mac",
        runner=q,
        cmd="true",  # comando exitoso que devuelve 0
        repo=tmp_path,
    )

    # forzar claim_next para que reclame esta tarea
    created = q.create("tarea")

    import subprocess as _sp

    def _run(*a, **k):
        class R:
            returncode = 0
            stdout = "commit: abc1234\n"
            stderr = ""

        return R()

    monkeypatch.setattr(_sp, "run", _run)
    ok = w.run_once()
    assert ok is True
    done = q.get(created.id)
    assert done.status == TaskStatus.DONE.value
    assert done.commit_sha == "abc1234"


def test_worker_run_once_fails(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="false", repo=tmp_path)
    created = q.create("tarea")

    import subprocess as _sp

    class R:
        returncode = 1
        stdout = ""
        stderr = "boom"

    monkeypatch.setattr(_sp, "run", lambda *a, **k: R())
    ok = w.run_once()
    assert ok is True
    assert q.get(created.id).status == TaskStatus.FAILED.value


def test_worker_run_once_timeout(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="sleep", repo=tmp_path)
    created = q.create("tarea")

    def _boom(task):
        raise WorkerError("Timeout ejecutando")

    monkeypatch.setattr(w, "_run_opencode", _boom)
    ok = w.run_once()
    assert ok is True
    assert q.get(created.id).status == TaskStatus.FAILED.value


def test_worker_run_once_no_work(tmp_path):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="true", repo=tmp_path)
    assert w.run_once() is False  # sin tareas → no ejecuta


def test_worker_steal_when_own_empty(tmp_path):
    q = _queue(tmp_path)
    created = q.create("tarea", node_id="gx10")
    w = NodeWorker(node_id="mac", runner=q, cmd="true", repo=tmp_path)
    # forzamos claim para testear solo el steal sin ejecutar opencode
    picked = w._queue.claim_next(w.agent, w.node_id)
    assert picked is not None
    assert picked.id == created.id


def test_worker_run_loop_and_stop(tmp_path):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="true", repo=tmp_path, poll_interval_s=0.05)

    def _stop_after():
        import time as _t

        _t.sleep(0.2)
        w.stop()

    threading.Thread(target=_stop_after, daemon=True).start()
    w.run()  # sale al llamarse stop()
    assert w._current_task_id is None


def test_worker_mark_present_absent(tmp_path):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="true", repo=tmp_path)
    w.mark_present()
    w.mark_absent()  # no debería lanzar


def test_worker_run_opencode_missing_cmd(tmp_path):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="no-such-binary-xyz", repo=tmp_path)
    created = q.create("tarea")
    ok = w.run_once()
    assert ok is True
    assert q.get(created.id).status == TaskStatus.FAILED.value


def test_worker_extract_commit():
    assert NodeWorker._extract_commit("x", "commit: abc1234\n") == "abc1234"
    assert NodeWorker._extract_commit("x", "commit abc1234 more\n") == "abc1234"
    assert NodeWorker._extract_commit("x", "no commit here\n") == ""


def test_worker_run_opencode_filenotfound(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="whatever", repo=tmp_path)
    created = _FakeTask("T-1", timeout=10)

    import subprocess as _sp

    def _raise(*a, **k):
        raise FileNotFoundError("no binary")

    monkeypatch.setattr(_sp, "run", _raise)
    try:
        w._run_opencode(created)
    except WorkerError as e:
        assert "No se encontró el ejecutor" in str(e)
    else:
        raise AssertionError("debió lanzar WorkerError")


def test_worker_run_opencode_timeout(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="x", repo=tmp_path)

    import subprocess as _sp

    def _raise(*a, **k):
        raise _sp.TimeoutExpired(cmd="x", timeout=10)

    monkeypatch.setattr(_sp, "run", _raise)
    try:
        w._run_opencode(_FakeTask("T-2", timeout=10))
    except WorkerError as e:
        assert "Timeout" in str(e)
    else:
        raise AssertionError("debió lanzar WorkerError")


def test_worker_run_opencode_truncate_and_fail(tmp_path, monkeypatch):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="x", repo=tmp_path)

    import subprocess as _sp

    class R:
        returncode = 1
        stdout = "x" * 5000
        stderr = ""

    monkeypatch.setattr(_sp, "run", lambda *a, **k: R())
    try:
        w._run_opencode(_FakeTask("T-3", timeout=10))
    except WorkerError as e:
        assert "exit=1" in str(e)
    else:
        raise AssertionError("debió lanzar WorkerError")


def test_worker_execute_start_returns_none(tmp_path):
    q = _queue(tmp_path)
    w = NodeWorker(node_id="mac", runner=q, cmd="true", repo=tmp_path)
    t = _FakeTask("T-4")
    # La tarea no está 'assigned' → start() devuelve None
    w._execute(t)
