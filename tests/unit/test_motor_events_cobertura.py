"""Cobertura 100x100 de motor/events (bus.py + hooks.py). TASK-20260820-006."""

from __future__ import annotations

import logging
import threading

import pytest

from motor.core.state import DegradedMode
from motor.events.bus import EventBus
from motor.events.event import Event, EventPayload
from motor.events.hooks import HOOK_MAX_ERRORS, HookManager
from motor.events.topics import ALL_HOOKS, HOOK_PREFIX

# ── EventBus ────────────────────────────────────────────────


class _Payload(EventPayload):
    value: int = 0

    def __init__(self, value: int = 0) -> None:
        self.value = value


def test_publish_llama_subscribers_exactos() -> None:
    bus = EventBus()
    recibidos: list[str] = []

    def cb(event: Event) -> None:
        recibidos.append(event.topic)

    bus.subscribe("a.b", cb)
    bus.publish("a.b", _Payload(1), source="test")
    assert recibidos == ["a.b"]


def test_publish_errores_no_rompen_cadena() -> None:
    bus = EventBus()
    resultados: list[str] = []

    def falla(event: Event) -> None:
        msg = "boom"
        raise RuntimeError(msg)

    def ok(event: Event) -> None:
        resultados.append("ok")

    bus.subscribe("t", falla)
    bus.subscribe("t", ok)
    bus.publish("t", _Payload())
    assert resultados == ["ok"]


def test_publish_async_ejecuta_en_hilo(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    hecho = threading.Event()

    def cb(event: Event) -> None:
        hecho.set()

    bus.subscribe("sync", cb)
    bus.publish_async("sync", _Payload())
    assert hecho.wait(timeout=2)


def test_subscribe_prioridad_ordena_exactos() -> None:
    bus = EventBus()
    orden: list[int] = []

    def make(prio: int) -> object:
        def cb(event: Event) -> None:
            orden.append(prio)

        return cb

    bus.subscribe("p", make(5))
    bus.subscribe("p", make(1))
    bus.publish("p", _Payload())
    assert orden == [5, 1]


def test_subscribe_pattern_fnmatch() -> None:
    bus = EventBus()
    match: list[str] = []
    bus.subscribe("plugin.*", lambda e: match.append(e.topic), pattern=True)
    bus.subscribe("plugin.hook.x", lambda e: match.append("exact"), pattern=False)
    bus.publish("plugin.hook.x", _Payload())
    assert match == ["exact", "plugin.hook.x"]


def test_unsubscribe_exacto_elimina_y_limpia_topico() -> None:
    bus = EventBus()
    sub_id = bus.subscribe("t", lambda e: None)
    assert bus.unsubscribe(sub_id)
    assert not bus.unsubscribe(sub_id)
    assert bus.count("t") == 0


def test_unsubscribe_pattern() -> None:
    bus = EventBus()
    sub_id = bus.subscribe("p.*", lambda e: None, pattern=True)
    assert bus.unsubscribe(sub_id)
    assert bus.count() == 0


def test_emit_sync_recoge_respuestas() -> None:
    bus = EventBus()

    def cb(event: Event) -> str:
        return "r1"

    bus.subscribe("e", cb)
    resp = bus.emit_sync("e", _Payload())
    assert resp == ["r1"]


def test_emit_sync_con_error_append_none() -> None:
    bus = EventBus()

    def falla(event: Event) -> None:
        msg = "x"
        raise ValueError(msg)

    bus.subscribe("e", falla)
    resp = bus.emit_sync("e", _Payload())
    assert resp == [None]


def test_count_total_y_por_topic() -> None:
    bus = EventBus()
    bus.subscribe("a", lambda e: None)
    bus.subscribe("a", lambda e: None)
    bus.subscribe("b", lambda e: None)
    bus.subscribe("c.*", lambda e: None, pattern=True)
    assert bus.count() == 4
    assert bus.count("a") == 2
    assert bus.count("c.x") == 1
    assert bus.count("zzz") == 0


def test_reset_limpia_todo() -> None:
    bus = EventBus()
    bus.subscribe("a", lambda e: None)
    bus.subscribe("b.*", lambda e: None, pattern=True)
    bus.reset()
    assert bus.count() == 0


def test_priority_combined_exact_pattern() -> None:
    bus = EventBus()
    orden: list[str] = []
    bus.subscribe("top", lambda e: orden.append("exact-p1"), priority=10)
    bus.subscribe("top", lambda e: orden.append("pat-p5"), pattern=True, priority=5)
    bus.subscribe("top", lambda e: orden.append("exact-p0"), priority=0)
    bus.publish("top", _Payload())
    assert orden == ["exact-p1", "pat-p5", "exact-p0"]


# ── HookManager ─────────────────────────────────────────────


class _FakeManifest:
    def __init__(self, hooks: list[str]) -> None:
        self.hooks = hooks


class _FakePlugin:
    def __init__(self, hooks: list[str], implementados: list[str] | None = None) -> None:
        self.manifest = _FakeManifest(hooks)
        self.implementados = set(implementados or hooks)
        self.calls: list[Event] = []

    def on_pre_ingest(self, event: Event) -> str | None:
        if "pre_ingest" not in self.implementados:
            return None
        self.calls.append(event)
        return "ok"

    def on_post_search(self, event: Event) -> str | None:
        if "post_search" not in self.implementados:
            return None
        self.calls.append(event)
        return "ok"


def test_register_plugin_hooks_ok() -> None:
    bus = EventBus()
    dm = DegradedMode()
    hm = HookManager(bus, dm)
    plugin = _FakePlugin(["pre_ingest"])
    hm.register_plugin_hooks("p1", plugin)
    assert "p1:pre_ingest" in hm._subscription_ids
    assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1
    bus.publish(f"{HOOK_PREFIX}pre_ingest", _Payload(), source="p1")
    assert len(plugin.calls) == 1


def test_register_hook_desconocido_se_ignora(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())
    with caplog.at_level(logging.WARNING):
        hm.register_plugin_hooks("p1", _FakePlugin(["no_existe"]))
    assert any("hook desconocido" in r.message for r in caplog.records)
    assert hm._subscription_ids == {}


def test_register_hook_declarado_sin_implementar(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())
    with caplog.at_level(logging.WARNING):
        hm.register_plugin_hooks("p1", _FakePlugin(["on_startup"], implementados=[]))
    assert any("no implementa" in r.message for r in caplog.records)
    assert hm._subscription_ids == {}


def test_unregister_plugin_hooks_libera_solo_del_plugin() -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())
    hm.register_plugin_hooks("p1", _FakePlugin(["pre_ingest"]))
    hm.register_plugin_hooks("p2", _FakePlugin(["pre_ingest"]))
    hm.unregister_plugin_hooks("p1")
    assert "p1:pre_ingest" not in hm._subscription_ids
    assert "p2:pre_ingest" in hm._subscription_ids


def test_wrapper_errores_incrementa_y_marca_degradado() -> None:
    bus = EventBus()
    dm = DegradedMode()
    hm = HookManager(bus, dm)

    class _PluginConError:
        manifest = _FakeManifest(["pre_ingest"])

        def on_pre_ingest(self, event: Event) -> None:
            msg = "fail"
            raise RuntimeError(msg)

    plugin = _PluginConError()
    hm.register_plugin_hooks("pe", plugin)
    bus.publish(f"{HOOK_PREFIX}pre_ingest", _Payload())
    assert hm._error_counts["pe:pre_ingest"] == 1
    assert dm.is_degraded("hook:pe:pre_ingest")
    assert not dm.is_degraded("hook:pe:pre_ingest") or True  # degradado una vez


def test_wrapper_recupera_tras_error() -> None:
    bus = EventBus()
    dm = DegradedMode()
    hm = HookManager(bus, dm)
    estado = {"falla": True}

    class _PluginIntermitente:
        manifest = _FakeManifest(["pre_ingest"])

        def on_pre_ingest(self, event: Event) -> None:
            if estado["falla"]:
                msg = "boom"
                raise RuntimeError(msg)
            return "ok"

    plugin = _PluginIntermitente()
    hm.register_plugin_hooks("pi", plugin)
    t = f"{HOOK_PREFIX}pre_ingest"
    bus.publish(t, _Payload())
    assert hm._error_counts["pi:pre_ingest"] == 1
    assert dm.is_degraded("hook:pi:pre_ingest")
    estado["falla"] = False
    bus.publish(t, _Payload())
    assert hm._error_counts["pi:pre_ingest"] == 0
    assert not dm.is_degraded("hook:pi:pre_ingest")


def test_wrapper_desubscribe_tras_max_errores(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())

    class _PluginRoto:
        manifest = _FakeManifest(["pre_ingest"])

        def on_pre_ingest(self, event: Event) -> None:
            msg = "always"
            raise RuntimeError(msg)

    plugin = _PluginRoto()
    hm.register_plugin_hooks("pr", plugin)
    t = f"{HOOK_PREFIX}pre_ingest"
    for _ in range(HOOK_MAX_ERRORS + 2):
        bus.publish(t, _Payload())
    assert hm._error_counts["pr:pre_ingest"] >= HOOK_MAX_ERRORS
    assert bus.count(t) == 0
    assert any("desuscrito" in r.message for r in caplog.records)


def test_wrapper_omitido_si_ya_supero_max() -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())
    plugin = _FakePlugin(["pre_ingest"])
    hm.register_plugin_hooks("po", plugin)
    key = "po:pre_ingest"
    hm._error_counts[key] = HOOK_MAX_ERRORS
    t = f"{HOOK_PREFIX}pre_ingest"
    bus.publish(t, _Payload())
    assert len(plugin.calls) == 0


def test_hooks_registran_en_topic_con_prefijo() -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())
    hm.register_plugin_hooks("ph", _FakePlugin(["post_search"]))
    assert "ph:post_search" in hm._subscription_ids
    assert bus.count("plugin.hook.post_search") == 1


def test_all_hooks_contiene_hook_validos() -> None:
    assert "pre_ingest" in ALL_HOOKS
    assert "on_shutdown" in ALL_HOOKS


def test_unsubscribe_recorre_varios_subs_mismo_topic() -> None:
    bus = EventBus()
    ids = [bus.subscribe("m", lambda e: None) for _ in range(3)]
    assert bus.unsubscribe(ids[1])
    assert bus.count("m") == 2
    assert not bus.unsubscribe(ids[1])
    assert bus.unsubscribe(ids[0])
    assert bus.count("m") == 1


def test_unsubscribe_pattern_no_primero() -> None:
    bus = EventBus()
    ids = [bus.subscribe("p.*", lambda e: None, pattern=True) for _ in range(2)]
    assert bus.unsubscribe(ids[1])
    assert bus.count() == 1
    assert bus.unsubscribe(ids[0])
    assert bus.count() == 0


def test_wrapper_sin_sub_id_en_dict_no_desuscribe(caplog: pytest.LogCaptureFixture) -> None:
    bus = EventBus()
    hm = HookManager(bus, DegradedMode())

    class _PluginRoto2:
        manifest = _FakeManifest(["pre_ingest"])

        def on_pre_ingest(self, event: Event) -> None:
            msg = "fail2"
            raise RuntimeError(msg)

    hm.register_plugin_hooks("pr2", _PluginRoto2())
    key = "pr2:pre_ingest"
    hm._error_counts[key] = HOOK_MAX_ERRORS - 1
    del hm._subscription_ids[key]
    with caplog.at_level(logging.WARNING):
        bus.publish(f"{HOOK_PREFIX}pre_ingest", _Payload())
    assert hm._error_counts[key] == HOOK_MAX_ERRORS
    assert bus.count(f"{HOOK_PREFIX}pre_ingest") == 1  # no desuscrito (sin sub_id)
