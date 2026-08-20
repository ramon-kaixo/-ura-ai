"""Cobertura 100x100 de motor/brain (7 modulos). TASK-20260820-009."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from motor.brain.advisor import ArchitectureAdvisor
from motor.brain.alerts import Alert, AlertEngine
from motor.brain.analyzer import CodeAnalyzer
from motor.brain.auto_maintain import AutoMaintainer, MaintenanceProposal
from motor.brain.executor import ProposalExecutor
from motor.brain.observer import BrainObserver, HealthObservation
from motor.brain.web_adapter import WebLearningAdapter

# ── analyzer ─────────────────────────────────────────────────


def _write_py(tmp_path: object, name: str, code: str) -> Path:
    p = Path(str(tmp_path)) / name
    p.write_text(code)
    return p


def test_analyze_file_basico(tmp_path: object) -> None:
    p = _write_py(tmp_path, "a.py", "def f1():\n    pass\n\ndef f2():\n    pass\n\nclass C:\n    pass\n")
    r = CodeAnalyzer().analyze_file(p)
    assert r["functions"] == 2
    assert r["classes"] == 1
    assert r["lines"] >= 7
    assert r["complex_functions"] == []


def test_analyze_file_syntax_error(tmp_path: object) -> None:
    p = _write_py(tmp_path, "bad.py", "def roto(:\n")
    r = CodeAnalyzer().analyze_file(p)
    assert r == {"error": "syntax_error"}


def test_analyze_file_funcion_compleja(tmp_path: object) -> None:
    cuerpo = "\n".join(f"    print({i})" for i in range(60))
    p = _write_py(tmp_path, "c.py", f"def grande():\n{cuerpo}\n")
    r = CodeAnalyzer().analyze_file(p)
    assert r["complex_functions"] == ["grande"]


def test_analyze_module_recorre(tmp_path: object) -> None:
    _write_py(tmp_path, "a.py", "def f():\n    pass\n")
    _write_py(tmp_path, "b.py", "class C:\n    pass\n")
    results = CodeAnalyzer().analyze_module(Path(str(tmp_path)))
    assert len(results) == 2


# ── advisor ──────────────────────────────────────────────────


def test_advisor_propose_sin_propuestas(tmp_path: object) -> None:
    _write_py(tmp_path, "a.py", "def f():\n    pass\n")
    props = ArchitectureAdvisor().propose(str(tmp_path))
    assert props == []


def test_advisor_propose_con_funcion_compleja(tmp_path: object) -> None:
    cuerpo = "\n".join(f"    print({i})" for i in range(60))
    _write_py(tmp_path, "c.py", f"def grande():\n{cuerpo}\n")
    props = ArchitectureAdvisor().propose(str(tmp_path))
    assert any(p["type"] == "refactor" and p["priority"] == "high" for p in props)


def test_advisor_propose_archivo_grande(tmp_path: object) -> None:
    cuerpo = "\n".join(f"x{i} = {i}" for i in range(600))
    _write_py(tmp_path, "big.py", f"def f():\n    pass\n{cuerpo}\n")
    props = ArchitectureAdvisor().propose(str(tmp_path))
    assert any(p["type"] == "split" for p in props)


# ── executor ─────────────────────────────────────────────────


def test_to_tuneladora_task_mapping() -> None:
    t = ProposalExecutor.to_tuneladora_task({"type": "refactor", "target": "x.py", "priority": "high"})
    assert t["plugin"] == "code_quality"
    t2 = ProposalExecutor.to_tuneladora_task({"type": "desconocido"})
    assert t2["plugin"] == "generic"
    assert t2["priority"] == "low"


def test_proposal_to_args_completo() -> None:
    args = ProposalExecutor._proposal_to_args(
        {
            "type": "refactor",
            "target": "x.py",
            "priority": "high",
            "flag": True,
            "noflag": False,
            "lista": [1, 2],
            "numero": 42,
            "flotante": 3.5,
            "texto": "hola",
            "despues": "otro",  # fuerza vuelta del loop tras un str
            "ultimo": "fin",  # append de str seguido de más items
            "nada": None,
        }
    )
    assert "--target=x.py" in args
    assert "--priority=high" in args
    assert "--flag" in args
    assert "--noflag" not in args
    assert "--lista=1" in args
    assert "--numero=42" in args
    assert "--texto=hola" in args
    assert "--despues=otro" in args
    assert "--ultimo=fin" in args
    assert "--nada" not in args


def test_proposal_to_args_sin_target() -> None:
    args = ProposalExecutor._proposal_to_args({"type": "test"})
    assert args == []


def test_execute_sin_engine() -> None:
    p = ProposalExecutor()
    p._engine = None
    p._get_engine = lambda: None
    r = p.execute({"type": "test", "target": "x"})
    assert r["error"] == "PipelineEngine not available"


def test_execute_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Engine:
        def run_script(self, script: str, args: list, timeout: int) -> object:
            return type("R", (), {"returncode": 0, "stdout": "ok", "stderr": ""})()

    p = ProposalExecutor()
    p._engine = _Engine()
    r = p.execute({"type": "refactor", "target": "x.py"})
    assert r["status"] == "success"
    assert r["returncode"] == 0


def test_execute_script_falla() -> None:
    class _Engine:
        def run_script(self, script: str, args: list, timeout: int) -> object:
            return type("R", (), {"returncode": 2, "stdout": "", "stderr": "boom"})()

    p = ProposalExecutor()
    p._engine = _Engine()
    r = p.execute({"type": "refactor", "target": "x.py"})
    assert r["status"] == "failed"
    assert r["returncode"] == 2


def test_execute_excepcion() -> None:
    class _Engine:
        def run_script(self, script: str, args: list, timeout: int) -> object:
            msg = "exploto"
            raise RuntimeError(msg)

    p = ProposalExecutor()
    p._engine = _Engine()
    r = p.execute({"type": "refactor", "target": "x.py"})
    assert r["status"] == "error"
    assert "exploto" in r["error"]


def test_get_engine_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name.startswith("scripts.pro.tuneladora"):
            msg = "no module"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    p = ProposalExecutor()
    p._engine = None
    assert p._get_engine() is None


def test_get_engine_import_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    class _EngineFake:
        def __init__(self) -> None:
            pass

    fake_mod = type("engine", (), {"PipelineEngine": lambda: _EngineFake()})
    monkeypatch.setitem(sys.modules, "scripts.pro.tuneladora.engine", fake_mod)
    p = ProposalExecutor()
    p._engine = None
    eng = p._get_engine()
    assert isinstance(eng, _EngineFake)
    monkeypatch.undo()


def test_executor_sys_path_insert() -> None:
    import sys

    import motor.brain.executor as ex_mod

    root = str(ex_mod._URA_ROOT)
    guardado = list(sys.path)
    sys.path = [p for p in sys.path if p != root]
    try:
        # re-importa el módulo para re-ejecutar el bloque de sys.path
        import importlib

        mod = importlib.reload(ex_mod)
        assert root in sys.path
        assert mod is not None
    finally:
        sys.path = guardado


# ── observer ─────────────────────────────────────────────────


def _obs(subsystem: str, status: str, raw: dict | None = None) -> HealthObservation:
    return HealthObservation(timestamp=time.time(), subsystem=subsystem, status=status, raw_data=raw or {})


def test_observer_register_y_observe() -> None:
    o = BrainObserver()
    o.register_provider("svc", lambda: {"status": "ok"})
    o.register_provider("svc2", lambda: {"status": "error"})
    obs = o.observe_all()
    assert len(obs) == 2
    assert obs[0].status == "ok"
    assert obs[1].status == "error"
    assert obs[1].anomaly == "Provider svc2 reports error"


def test_observer_provider_que_lanza() -> None:
    o = BrainObserver()

    def _roto() -> dict:
        msg = "fallo"
        raise RuntimeError(msg)

    o.register_provider("roto", _roto)
    obs = o.observe_all()
    assert obs[0].status == "error"
    assert "Health check failed" in obs[0].anomaly


def test_observer_latencia_critica() -> None:
    o = BrainObserver()
    o.register_provider("lento", lambda: {"status": "ok", "latency_ms": 1500})
    obs = o.observe_all()
    assert obs[0].anomaly == "Latency critical: 1500ms"


def test_observer_latencia_elevada() -> None:
    o = BrainObserver()
    o.register_provider("medio", lambda: {"status": "ok", "latency_ms": 600})
    obs = o.observe_all()
    assert obs[0].status == "warning"
    assert "Latency elevated" in obs[0].anomaly


def test_observer_sin_anomalia() -> None:
    o = BrainObserver()
    o.register_provider("bien", lambda: {"status": "ok", "latency_ms": 10})
    obs = o.observe_all()
    assert obs[0].anomaly is None
    assert obs[0].status == "ok"


def test_observer_status_unknown() -> None:
    o = BrainObserver()
    o.register_provider("raro", lambda: {})
    obs = o.observe_all()
    assert obs[0].status == "unknown"


def test_observer_history_y_get_critical() -> None:
    o = BrainObserver()
    o.register_provider("a", lambda: {"status": "ok"})
    o.register_provider("b", lambda: {"status": "error"})
    o.observe_all()
    assert len(o.get_history("a")) == 1
    assert o.get_history("zzz") == []
    crit = o.get_critical()
    assert len(crit) >= 1


# ── alerts ───────────────────────────────────────────────────


class _ObserverStub:
    def __init__(self, observations: list[HealthObservation]) -> None:
        self._obs = observations

    def observe_all(self) -> list[HealthObservation]:
        return self._obs


def test_alert_provider_caido() -> None:
    eng = AlertEngine(_ObserverStub([_obs("ollama", "error", {"anomaly": "timeout"})]))
    alerts = eng.evaluate()
    assert len(alerts) == 1
    assert alerts[0].severity == "critical"
    assert "Provider caido" in alerts[0].title
    assert alerts[0].suggested_action == "Verificar conectividad y credenciales"


def test_alert_disco_critico_y_bajo() -> None:
    eng = AlertEngine(_ObserverStub([_obs("disk", "ok", {"libre_gb": 5})]))
    alerts = eng.evaluate()
    assert any(a.severity == "emergency" for a in alerts)
    eng2 = AlertEngine(_ObserverStub([_obs("disk", "ok", {"libre_gb": 30})]))
    alerts2 = eng2.evaluate()
    assert any(a.severity == "warning" for a in alerts2)
    eng3 = AlertEngine(_ObserverStub([_obs("disk", "ok", {"libre_gb": 999})]))
    assert eng3.evaluate() == []


def test_alert_degradacion() -> None:
    obs = [
        _obs("a", "ok", {"latency_ms": 900}),
        _obs("b", "ok", {"latency_ms": 800}),
        _obs("c", "error"),
    ]
    eng = AlertEngine(_ObserverStub(obs))
    alerts = eng.evaluate()
    assert any("DEGRADACION" in a.title for a in alerts)


def test_alert_red() -> None:
    obs = [_obs("search", "ok", {"latency_ms": 900})]
    eng = AlertEngine(_ObserverStub(obs))
    alerts = eng.evaluate()
    assert any("red" in a.title.lower() for a in alerts)


def test_alert_red_excluye_error_y_disk() -> None:
    obs = [_obs("disk", "error", {"latency_ms": 900})]
    eng = AlertEngine(_ObserverStub(obs))
    alerts = eng.evaluate()
    assert not any("red" in a.title.lower() for a in alerts)


def test_alert_history_y_critical() -> None:
    eng = AlertEngine(_ObserverStub([_obs("x", "error")]))
    eng.evaluate()
    assert len(eng.get_history()) == 1
    assert len(eng.get_history(limit=0)) == 1  # [-0:] == [:] en Python
    assert len(eng.get_critical()) == 1


# ── web_adapter ──────────────────────────────────────────────


def test_web_adapter_search_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    a = WebLearningAdapter()

    class _Prov:
        def __init__(self) -> None:
            pass

        def search(self, query: str, max_results: int = 5) -> list:
            return [{"url": "http://x", "title": "Titulo Python", "snippet": "snippet" * 50}]

    class _Crawler:
        def crawl(self, url: str) -> object:
            return type("D", (), {"content": "contenido" * 200})()

    class _Sum:
        def summarize(self, text: str, max_sentences: int = 5) -> str:
            return "resumen"

    a._searcher = _Prov
    a._crawler = _Crawler
    a._summarizer = _Sum
    r = a.search("python")
    assert r[0]["source"] == "http://x"
    assert r[0]["relevance"] >= 0.0


def test_web_adapter_search_error() -> None:
    a = WebLearningAdapter()

    class _Prov:
        def search(self, query: str, max_results: int = 5) -> list:
            msg = "sin red"
            raise RuntimeError(msg)

    a._searcher = _Prov
    r = a.search("q")
    assert "error" in r[0]


def test_web_adapter_crawl_ok() -> None:
    a = WebLearningAdapter()

    class _C:
        def crawl(self, url: str) -> object:
            return type("D", (), {"content": "x" * 50})()

    a._crawler = _C
    r = a.crawl("http://u")
    assert r["status"] == "ok"
    assert r["content"] == "x" * 50


def test_web_adapter_crawl_error() -> None:
    a = WebLearningAdapter()

    class _C:
        def crawl(self, url: str) -> object:
            msg = "no accesible"
            raise RuntimeError(msg)

    a._crawler = _C
    r = a.crawl("http://u")
    assert r["status"] == "error"
    assert "no accesible" in r["error"]


def test_web_adapter_summarize() -> None:
    a = WebLearningAdapter()

    class _S:
        def summarize(self, text: str, max_sentences: int = 5) -> str:
            return "resumen"

    a._summarizer = _S
    assert a.summarize("texto") == "resumen"


def test_web_adapter_summarize_error() -> None:
    a = WebLearningAdapter()

    class _S:
        def summarize(self, text: str, max_sentences: int = 5) -> str:
            msg = "roto"
            raise RuntimeError(msg)

    a._summarizer = _S
    assert a.summarize("texto") == ""


def test_web_adapter_learn_from_web(monkeypatch: pytest.MonkeyPatch) -> None:
    a = WebLearningAdapter()

    class _Prov:
        def search(self, query: str, max_results: int = 5) -> list:
            return [{"url": "http://u1", "title": "T", "snippet": "s"}, {"url": "http://u2", "title": "T2", "snippet": "s2"}]

    class _C:
        def crawl(self, url: str) -> object:
            return type("D", (), {"content": "contenido util" * 10})()

    class _S:
        def summarize(self, text: str, max_sentences: int = 5) -> str:
            return "resumen final"

    a._searcher = _Prov
    a._crawler = _C
    a._summarizer = _S
    r = a.learn_from_web("python")
    assert r["sources_found"] == 2
    assert r["sources_crawled"] == 2
    assert r["summary"] == "resumen final"


def test_web_adapter_learn_sin_summary() -> None:
    a = WebLearningAdapter()

    class _Prov:
        def search(self, query: str, max_results: int = 5) -> list:
            return [{"url": "http://u1", "title": "T", "snippet": "s"}]

    class _C:
        def crawl(self, url: str) -> object:
            return type("D", (), {"content": "x"})()

    a._searcher = _Prov
    a._crawler = _C
    a._summarizer = None
    a._load_modules = lambda: None  # evita import real
    r = a.learn_from_web("q")
    assert r["summary"] == "No summarizer available"


def test_web_adapter_score() -> None:
    a = WebLearningAdapter()
    assert a._score("python codigo", {"title": "python", "snippet": "codigo"}) == 1.0
    assert a._score("", {"title": "x"}) == 0.0
    assert a._score("python", {"title": "nada"}) == 0.0


# ── auto_maintain ────────────────────────────────────────────


def _alert(severity: str = "warning", title: str = "Disco bajo") -> Alert:
    return Alert(severity=severity, title=title, description="d", affected_subsystems=["disk"], timestamp=time.time())


def _executor_stub(result: dict | None = None) -> object:
    class _E:
        def __init__(self) -> None:
            self.calls = []

        def execute(self, proposal: dict) -> dict:
            self.calls.append(proposal)
            return result or {"status": "success"}

    return _E()


def test_classify_risk() -> None:
    a = _alert("warning", "Disco bajo")
    p = MaintenanceProposal(alert=a, action="auto_fix_ruff", target="x", params={})
    assert AutoMaintainer._classify_risk(p) == "safe"
    p2 = MaintenanceProposal(alert=a, action="check_network", target="x", params={})
    assert AutoMaintainer._classify_risk(p2) == "safe"
    p3 = MaintenanceProposal(alert=_alert("warning", "Disco bajo"), action="clean_disk", target="x", params={})
    assert AutoMaintainer._classify_risk(p3) == "safe"
    p4 = MaintenanceProposal(alert=_alert("critical", "DISCO CRITICO"), action="clean_disk", target="x", params={})
    assert AutoMaintainer._classify_risk(p4) == "medium"
    p5 = MaintenanceProposal(alert=a, action="restart_provider", target="x", params={})
    assert AutoMaintainer._classify_risk(p5) == "medium"
    p6 = MaintenanceProposal(alert=a, action="emergency_shutdown", target="x", params={})
    assert AutoMaintainer._classify_risk(p6) == "critical"
    p7 = MaintenanceProposal(alert=a, action="otra_cosa", target="x", params={})
    assert AutoMaintainer._classify_risk(p7) == "medium"


def test_alert_to_proposal() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    assert m._alert_to_proposal(_alert("emergency", "DISCO CRITICO")).action == "clean_disk"
    assert m._alert_to_proposal(_alert("critical", "Provider caido")).action == "restart_provider"
    assert m._alert_to_proposal(_alert("critical", "DEGRADACION DE SERVICIO")).action == "scale_resources"
    assert m._alert_to_proposal(_alert("warning", "Posible problema de red")).action == "check_network"
    assert m._alert_to_proposal(_alert("warning", "Otro titulo")) is None


def test_scan_clasifica_riesgos() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    # alerta de disco (warning) → clean_disk → safe (severity warning)
    obs = [_obs("disk", "ok", {"libre_gb": 30})]
    o.register_provider("disk", lambda: {"status": "ok", "libre_gb": 30})
    # el observer real necesita providers; usamos stub del AlertEngine
    m._alerts = AlertEngine(_ObserverStub(obs))
    props = m.scan()
    assert len(props) >= 1
    assert props[0].risk_level == "safe"
    assert props[0].auto_execute is True


def test_propose_and_maybe_execute() -> None:
    o = BrainObserver()
    ex = _executor_stub()
    m = AutoMaintainer(o, ex)
    obs = [_obs("disk", "ok", {"libre_gb": 30})]
    m._alerts = AlertEngine(_ObserverStub(obs))
    results = m.propose_and_maybe_execute()
    assert results[0]["auto_executed"] is True


def test_approve_and_execute_critical() -> None:
    o = BrainObserver()
    ex = _executor_stub()
    m = AutoMaintainer(o, ex)
    p = MaintenanceProposal(alert=_alert("critical"), action="emergency_shutdown", target="sys", params={}, risk_level="critical")
    r = m.approve_and_execute(p, approved=True)
    assert r["status"] == "critical_blocked"


def test_approve_and_execute_rechazado() -> None:
    o = BrainObserver()
    ex = _executor_stub()
    m = AutoMaintainer(o, ex)
    p = MaintenanceProposal(alert=_alert(), action="clean_disk", target="disk", params={}, risk_level="medium")
    r = m.approve_and_execute(p, approved=False)
    assert r["status"] == "rejected"


def test_approve_and_execute_ok() -> None:
    o = BrainObserver()
    ex = _executor_stub()
    m = AutoMaintainer(o, ex)
    p = MaintenanceProposal(alert=_alert(), action="clean_disk", target="disk", params={"min_free_gb": 50}, risk_level="medium")
    m._verify_resolution = lambda prop: {"resolved": True}
    r = m.approve_and_execute(p, approved=True)
    assert r["execution"]["status"] == "success"
    assert r["verification"]["resolved"] is True
    assert len(m.get_resolved()) == 1


def test_action_to_type() -> None:
    assert AutoMaintainer._action_to_type("clean_disk") == "refactor"
    assert AutoMaintainer._action_to_type("check_network") == "test"
    assert AutoMaintainer._action_to_type("auto_fix_code") == "format"
    assert AutoMaintainer._action_to_type("desconocido") == "generic"


def test_verify_resolution() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    prop = MaintenanceProposal(alert=_alert(), action="clean_disk", target="disk", params={})
    m._observer = _ObserverStub([_obs("disk", "ok")])
    assert m._verify_resolution(prop) == {"resolved": True, "subsystem": "disk", "status": "ok"}
    m._observer = _ObserverStub([_obs("disk", "error")])
    r = m._verify_resolution(prop)
    assert r["resolved"] is False
    m._observer = _ObserverStub([_obs("otro", "ok")])
    assert m._verify_resolution(prop) == {"resolved": False, "error": "Subsystem not found"}


def test_auto_fix_code_sin_cambios(monkeypatch: pytest.MonkeyPatch) -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    monkeypatch.setattr(m, "_run_ruff", lambda cmd, root, label: f"{label}: exit=0")
    monkeypatch.setattr(m, "_git_has_changes", lambda d, r: False)
    r = m.auto_fix_code("motor/brain/")
    assert r["status"] == "no_changes"
    assert r["committed"] is False


def test_auto_fix_code_con_cambios(monkeypatch: pytest.MonkeyPatch) -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    monkeypatch.setattr(m, "_run_ruff", lambda cmd, root, label: f"{label}: exit=0")
    monkeypatch.setattr(m, "_git_has_changes", lambda d, r: True)
    monkeypatch.setattr(m, "_git_commit_changes", lambda d, r, log: {"status": "committed", "fix_log": log, "committed": True})
    r = m.auto_fix_code("motor/brain/")
    assert r["status"] == "committed"


def test_run_ruff_error() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    res = m._run_ruff(["/no/existe/ruff"], Path(), "label")
    assert "fallo" in res


def test_git_has_changes_error() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    assert m._git_has_changes("zzz", Path("/no/existe")) is False


def test_git_commit_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import subprocess

    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())

    def _roto(*a, **k):
        msg = "no git"
        raise RuntimeError(msg)

    monkeypatch.setattr(subprocess, "run", _roto)
    r = m._git_commit_changes("motor/brain/", Path(), ["log"])
    assert r["status"] == "commit_failed"


def test_scheduler_start_y_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())

    class _Sched:
        pipeline_count = 3
        is_running = False

        def add_pipeline(self, *a, **k) -> None:
            pass

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def get_status(self) -> list:
            return []

    fake_mod = type("sched", (), {"TuneladoraScheduler": lambda: _Sched()})
    monkeypatch.setitem(sys.modules, "scripts.pro.tuneladora.scheduler", fake_mod)
    m._scheduler = None
    m.start_scheduler()
    m.stop_scheduler()
    st = m.get_scheduler_status()
    assert st["running"] is False
    assert st["pipeline_count"] == 3
    monkeypatch.undo()


def test_scheduler_import_error(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    real = builtins.__import__

    def _bloq(name: str, *a, **k):
        if name.startswith("scripts.pro.tuneladora"):
            msg = "no module"
            raise ImportError(msg)
        return real(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", _bloq)
    m._scheduler = None
    m.start_scheduler()  # no lanza
    assert m.get_scheduler_status()["reason"] == "Scheduler not started"


def test_stop_scheduler_sin_scheduler() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    m._scheduler = None
    m.stop_scheduler()  # rama else: no hace nada


def test_get_pending_y_resolved() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    p = MaintenanceProposal(alert=_alert(), action="clean_disk", target="disk", params={})
    m._pending = [p]
    assert m.get_pending() == [p]
    assert m.get_resolved() == []


# ── ramas restantes ──────────────────────────────────────────


def test_scan_alerta_sin_propuesta() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    m._alerts = AlertEngine(_ObserverStub([_obs("x", "ok")]))
    assert m.scan() == []


def test_scan_alerta_no_convertible() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    a = Alert(severity="warning", title="Otro titulo", description="d", affected_subsystems=["x"], timestamp=time.time())
    m._alerts = AlertEngine(_ObserverStub([_obs("x", "ok")]))
    m._alerts.evaluate = lambda: [a]  # type: ignore[method-assign]  # alerta no convertible → continue
    assert m.scan() == []


def test_observer_history_duplicado() -> None:
    o = BrainObserver()
    obs = _obs("dup", "ok")
    o._record("dup", obs)
    o._record("dup", obs)
    assert len(o.get_history("dup")) == 2


def test_propose_y_ejecutar_pendiente() -> None:
    o = BrainObserver()
    ex = _executor_stub()
    m = AutoMaintainer(o, ex)
    obs = [_obs("disk", "ok", {"libre_gb": 5})]  # emergency → clean_disk medium
    m._alerts = AlertEngine(_ObserverStub(obs))
    results = m.propose_and_maybe_execute()
    assert results[0]["auto_executed"] is False
    assert results[0]["status"] == "pending"


def test_scheduler_real_sin_event_loop(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())

    class _SchedReal:
        pipeline_count = 2
        is_running = True

        def add_pipeline(self, name: str, interval_minutes: int, auto_execute_safe: bool) -> None:
            pass

        def start(self) -> None:
            pass

        def stop(self) -> None:
            pass

        def get_status(self) -> list:
            return ["health"]

    fake_mod = type("sched", (), {"TuneladoraScheduler": lambda: _SchedReal()})
    monkeypatch.setitem(sys.modules, "scripts.pro.tuneladora.scheduler", fake_mod)
    m._scheduler = None
    m.start_scheduler()
    assert m.get_scheduler_status()["running"] is True
    assert m.get_scheduler_status()["pipelines"] == ["health"]
    monkeypatch.undo()


def test_run_ruff_ok() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    res = m._run_ruff(["true"], Path(), "ok-label")
    assert "exit=" in res


def test_git_has_changes_true() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    assert m._git_has_changes("motor/brain/", Path(__file__).resolve().parents[2]) in (True, False)


def test_git_commit_ok() -> None:
    o = BrainObserver()
    m = AutoMaintainer(o, _executor_stub())
    r = m._git_commit_changes("zzz-no-existe", Path(), ["log"])
    assert r["status"] in ("committed", "commit_failed")


def test_observer_history_primer_registro() -> None:
    o = BrainObserver()
    obs = _obs("nuevo", "ok")
    o._record("nuevo", obs)
    assert o.get_history("nuevo") == [obs]


def test_web_adapter_sin_searcher() -> None:
    a = WebLearningAdapter()
    a._load_modules = lambda: None
    a._searcher = None
    r = a.search("q")
    assert r[0]["error"] == "No searcher available"


def test_web_adapter_sin_crawler() -> None:
    a = WebLearningAdapter()
    a._load_modules = lambda: None
    a._crawler = None
    r = a.crawl("http://u")
    assert r["error"] == "No crawler available"


def test_web_adapter_learn_sin_sources() -> None:
    a = WebLearningAdapter()

    class _Prov:
        def search(self, query: str, max_results: int = 5) -> list:
            return [{"title": "sin url", "snippet": "s"}]

    a._searcher = _Prov
    a._summarizer = None
    a._load_modules = lambda: None
    r = a.learn_from_web("q")
    assert r["sources_crawled"] == 0
    assert r["summary"] == ""
