"""Tests de cobertura para motor/scanner/diff_detector.py (gate 85%, meta 100)."""

from __future__ import annotations

from motor.scanner.diff_detector import _es_critico, compute_diff


class TestComputeDiff:
    def test_sin_cambios(self) -> None:
        prev = {"servicios": {"ollama": "active"}, "recursos": {"ram_pct": 50}}
        actual = dict(prev)
        count, anomalias = compute_diff(actual, prev)
        assert count == 0
        assert anomalias == []

    def test_cambio_no_critico(self) -> None:
        prev = {"recursos": {"ram_pct": 40}}
        actual = {"recursos": {"ram_pct": 55}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1
        assert anomalias == []

    def test_servicio_caido_critico(self) -> None:
        prev = {"servicios": {"ollama": "active"}}
        actual = {"servicios": {"ollama": "failed"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1
        assert anomalias == ["servicios.ollama: active -> failed"]

    def test_ram_alta_critica(self) -> None:
        prev = {"recursos": {"ram_pct": 50}}
        actual = {"recursos": {"ram_pct": 95}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1
        assert anomalias == ["recursos.ram_pct: 50 -> 95"]

    def test_clave_nueva_ignorada(self) -> None:
        prev: dict = {"servicios": {"a": "active"}}
        actual: dict = {"servicios": {"a": "active"}, "nuevo": "x"}
        count, anomalias = compute_diff(actual, prev)
        assert count == 0
        assert anomalias == []

    def test_anidado_vacio_prev(self) -> None:
        prev: dict = {"servicios": {}}
        actual: dict = {"servicios": {"a": "active"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 1
        assert anomalias == []

    def test_clave_en_prev_no_en_actual_ignorada(self) -> None:
        prev: dict = {"servicios": {"a": "active"}, "perdido": {"x": 1}}
        actual: dict = {"servicios": {"a": "active"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 0
        assert anomalias == []

    def test_mixto_prev_dict_actual_no_dict_ignorado(self) -> None:
        prev: dict = {"servicios": {"a": "active"}}
        actual: dict = {"servicios": "caido"}
        count, anomalias = compute_diff(actual, prev)
        assert count == 0
        assert anomalias == []

    def test_mixto_prev_no_dict_actual_dict_ignorado(self) -> None:
        prev: dict = {"servicios": "active"}
        actual: dict = {"servicios": {"a": "active"}}
        count, anomalias = compute_diff(actual, prev)
        assert count == 0
        assert anomalias == []


class TestEsCritico:
    def test_servicio_inactive(self) -> None:
        assert _es_critico("servicios", "ollama", "active", "inactive")

    def test_servicio_unknown(self) -> None:
        assert _es_critico("servicios", "x", "active", "unknown")

    def test_servicio_active_no_critico(self) -> None:
        assert not _es_critico("servicios", "x", "failed", "active")

    def test_disk_alta(self) -> None:
        assert _es_critico("recursos", "disk_pct", 50, 91)

    def test_ram_justo_90_no_critico(self) -> None:
        assert not _es_critico("recursos", "ram_pct", 50, 90)

    def test_zombies_cero_no_critico(self) -> None:
        assert not _es_critico("recursos", "zombies", 1, 0)

    def test_zombies_positivo_critico(self) -> None:
        assert _es_critico("recursos", "zombies", 0, 2)

    def test_ram_str_no_critico(self) -> None:
        assert not _es_critico("recursos", "ram_pct", 50, "95")

    def test_hw_ok_false_critico(self) -> None:
        assert _es_critico("hw_health", "ok", True, False)

    def test_hw_ok_true_no_critico(self) -> None:
        assert not _es_critico("hw_health", "ok", False, True)

    def test_otra_categoria_no_critica(self) -> None:
        assert not _es_critico("red", "latencia", 10, 20)
