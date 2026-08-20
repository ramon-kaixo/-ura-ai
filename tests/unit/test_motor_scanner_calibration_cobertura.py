"""Cobertura 100x100 de motor/scanner/calibration.py (TASK-20260820-005).

Cubre: Calibration — carga/guardado baseline, detectar_anomalias, learn,
detect (z-score con warning/critico), casos borde (sin trends, sin baseline,
desv=0, datos no numericos, disco).

Usa tmp_path (pytest) y config fake; no toca disco real.
"""

from __future__ import annotations

import json

from motor.scanner.calibration import Calibration


class _Config:
    def __init__(self, baseline_path: str | None = None, data_dir: str = "") -> None:
        self.baseline_path = baseline_path
        self.data_dir = data_dir


class _Estado:
    def __init__(self, recursos: dict) -> None:
        self.recursos = recursos


def _calib(tmp_path, baseline_path=None, preexistente=None) -> Calibration:
    if baseline_path is None:
        baseline_path = str(tmp_path / "baseline_test.json")
    if preexistente is not None:
        (tmp_path / "baseline_test.json").write_text(json.dumps(preexistente))
    return Calibration(_Config(baseline_path=baseline_path, data_dir=str(tmp_path)))


class TestCarga:
    def test_sin_baseline_vacio(self, tmp_path) -> None:
        c = _calib(tmp_path)
        assert c.hay_baseline is False
        assert c._baseline == {}

    def test_carga_baseline_existente(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"ram_pct_max": 50})
        assert c.hay_baseline is True
        assert c._baseline["ram_pct_max"] == 50

    def test_baseline_corrupto(self, tmp_path) -> None:
        p = tmp_path / "baseline_test.json"
        p.write_text("no-json{")
        c = Calibration(_Config(baseline_path=str(p), data_dir=str(tmp_path)))
        assert c.hay_baseline is False

    def test_baseline_path_default_data_dir(self, tmp_path) -> None:
        c = Calibration(_Config(baseline_path=None, data_dir=str(tmp_path)))
        assert c.baseline_path == tmp_path / "baseline_inicial.json"


class TestDetectarAnomalias:
    def test_sin_baseline_no_anomalias(self, tmp_path) -> None:
        c = _calib(tmp_path)
        assert c.detectar_anomalias(_Estado({"ram_pct": 99})) == []

    def test_ram_supera_limite(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"ram_pct_max": 50})
        a = c.detectar_anomalias(_Estado({"ram_pct": 90}))
        assert len(a) == 1
        assert "Calib.ram_pct=90" in a[0]

    def test_dentro_de_limite(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"ram_pct_max": 50})
        assert c.detectar_anomalias(_Estado({"ram_pct": 30})) == []

    def test_disk_supera_limite(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"disk_pct_max": 70})
        a = c.detectar_anomalias(_Estado({"disk_pct": 90}))
        assert len(a) == 1
        assert "Calib.disk_pct=90" in a[0]

    def test_load_supera_limite(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"load_max": 3})
        a = c.detectar_anomalias(_Estado({"load_1m": 5.5}))
        assert len(a) == 1
        assert "Calib.load_1m=5.5" in a[0]

    def test_recursos_no_dict(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"ram_pct_max": 50})
        assert c.detectar_anomalias(_Estado(recursos=None)) == []

    def test_metricas_multiples(self, tmp_path) -> None:
        c = _calib(tmp_path, preexistente={"ram_pct_max": 10, "disk_pct_max": 10, "load_max": 1})
        a = c.detectar_anomalias(_Estado({"ram_pct": 90, "disk_pct": 90, "load_1m": 5}))
        assert len(a) == 3


class TestLearn:
    def test_learn_sin_trends(self, tmp_path) -> None:
        c = _calib(tmp_path)
        bl = c.learn(_Estado({"ram_pct": 50, "disk_pct": 40, "load_1m": 2}))
        assert bl["ram_pct_max"] == 60.0
        assert bl["disk_pct_max"] == 48.0
        assert bl["load_max"] == 3.0
        assert bl["puntos_trend"] == 0
        assert bl["generated"].endswith("Z")
        assert c.hay_baseline is True
        # persistido a disco
        assert (tmp_path / "baseline_test.json").exists()

    def test_learn_con_trends(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [
            {"ram_pct": 30, "disk_pct": 20, "load_1m": 1},
            {"ram_pct": 40, "disk_pct": 30, "load_1m": 2},
            {"ram_pct": 50, "disk_pct": 40, "load_1m": 3},
        ]
        bl = c.learn(_Estado({"ram_pct": 60, "disk_pct": 50, "load_1m": 4}), trends)
        assert bl["puntos_trend"] == 3
        assert "ram_pct_max" in bl
        assert isinstance(bl["ram_pct_max"], (int, float))
        assert "disk_pct_max" in bl
        assert "load_1m_max" in bl

    def test_learn_trends_con_valores_no_numericos(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [
            {"ram_pct": 30},
            {"ram_pct": "n/a", "disk_pct": None},
            {"ram_pct": 50},
            {"ram_pct": 60},
        ]
        bl = c.learn(_Estado({"ram_pct": 70}), trends)
        # 3 valores numericos -> ram_pct_max calculado con media/desv
        assert "ram_pct_max" in bl
        # disk y load sin valores numericos validos -> no se añaden
        assert "disk_pct_max" not in bl
        assert "load_1m_max" not in bl

    def test_learn_trends_2_no_entra_rama_stats(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [{"ram_pct": 30}, {"ram_pct": 40}]
        bl = c.learn(_Estado({"ram_pct": 50}), trends)
        assert bl["puntos_trend"] == 2


class TestDetect:
    def test_sin_trends(self, tmp_path) -> None:
        c = _calib(tmp_path)
        assert c.detect([]) == {"anomalias": [], "ok": True}

    def test_menos_de_3_puntos_skip(self, tmp_path) -> None:
        c = _calib(tmp_path)
        r = c.detect([{"ram_pct": 10}, {"ram_pct": 20}])
        assert r["anomalias"] == []
        assert r["ok"] is True
        assert r["total_puntos"] == 2

    def test_critico(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [{"ram_pct": 10}, {"ram_pct": 12}, {"ram_pct": 11}, {"ram_pct": 95}]
        r = c.detect(trends)
        assert len(r["anomalias"]) == 1
        assert r["anomalias"][0]["nivel"] == "critico"
        assert r["anomalias"][0]["metrica"] == "ram_pct"
        assert r["anomalias"][0]["z_score"] > 1
        assert r["ok"] is False

    def test_warning(self, tmp_path) -> None:
        c = _calib(tmp_path)
        # media=11, desv=1.0 -> warn=12.5, crit=13 -> 12.6 warning
        trends = [{"ram_pct": 10}, {"ram_pct": 12}, {"ram_pct": 11}, {"ram_pct": 12.6}]
        r = c.detect(trends)
        assert len(r["anomalias"]) == 1
        assert r["anomalias"][0]["nivel"] == "warning"

    def test_sin_anomalia(self, tmp_path) -> None:
        c = _calib(tmp_path)
        # media=11, desv=1.0 -> warn=12.5 -> 12.3 sin anomalia
        trends = [{"ram_pct": 10}, {"ram_pct": 12}, {"ram_pct": 11}, {"ram_pct": 12.3}]
        r = c.detect(trends)
        assert r["anomalias"] == []
        assert r["ok"] is True

    def test_desv_cero_usuario(self, tmp_path) -> None:
        c = _calib(tmp_path)
        # todos iguales -> desv=0 -> desv = media*0.1
        trends = [{"ram_pct": 50}, {"ram_pct": 50}, {"ram_pct": 50}, {"ram_pct": 60}]
        r = c.detect(trends)
        assert len(r["anomalias"]) == 1
        assert r["anomalias"][0]["desv"] > 0

    def test_desv_cero_critico(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [{"ram_pct": 50}, {"ram_pct": 50}, {"ram_pct": 50}, {"ram_pct": 500}]
        r = c.detect(trends)
        assert r["anomalias"][0]["nivel"] == "critico"

    def test_disk_y_load(self, tmp_path) -> None:
        c = _calib(tmp_path)
        trends = [{"disk_pct": 10}, {"disk_pct": 11}, {"disk_pct": 10}, {"disk_pct": 60}]
        r = c.detect(trends)
        assert any(a["metrica"] == "disk_pct" for a in r["anomalias"])

    def test_load_menos_3_puntos_skip(self, tmp_path) -> None:
        c = _calib(tmp_path)
        # solo 2 valores de load -> len(vals)<3 -> skip (sin anomalias)
        trends = [{"load_1m": 1}, {"load_1m": 2}]
        r = c.detect(trends)
        assert r["anomalias"] == []

    def test_detect_solo_un_valor_desv_media(self, tmp_path) -> None:
        c = _calib(tmp_path)
        # con 3 puntos: media de vals[:-1] y desv = media*0.1
        r = c.detect([{"ram_pct": 30}, {"ram_pct": 30}, {"ram_pct": 100}])
        assert r["anomalias"][0]["nivel"] == "critico"
