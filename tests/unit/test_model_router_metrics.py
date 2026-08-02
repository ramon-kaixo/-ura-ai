"""Tests for core/model_router/metrics.py."""

from core.model_router.metrics import MetricsCollector


class TestIncrement:
    def test_sin_labels(self):
        m = MetricsCollector()
        m.increment("reqs")
        assert m.metrics["reqs"]["count"] == 1
        m.increment("reqs")
        assert m.metrics["reqs"]["count"] == 2

    def test_con_labels_orden_independiente(self):
        m = MetricsCollector()
        m.increment("reqs", {"b": "2", "a": "1"})
        m.increment("reqs", {"a": "1", "b": "2"})
        assert m.metrics['reqs{a="1",b="2"}']['count'] == 2

    def test_labels_distintos_son_series_distintas(self):
        m = MetricsCollector()
        m.increment("reqs", {"modelo": "a"})
        m.increment("reqs", {"modelo": "b"})
        assert m.metrics['reqs{modelo="a"}']['count'] == 1
        assert m.metrics['reqs{modelo="b"}']['count'] == 1

    def test_last_updated_presente(self):
        m = MetricsCollector()
        m.increment("reqs")
        assert "last_updated" in m.metrics["reqs"]


class TestRecordLatency:
    def test_media_calculada(self):
        m = MetricsCollector()
        m.record_latency("lat", 10.0)
        m.record_latency("lat", 30.0)
        assert m.metrics["lat"]["latency_sum"] == 40.0
        assert m.metrics["lat"]["latency_count"] == 2
        assert m.metrics["lat"]["latency_avg"] == 20.0

    def test_historial_append(self):
        m = MetricsCollector()
        m.record_latency("lat", 1.0)
        m.record_latency("lat", 2.0)
        assert m.metrics_history["lat"] == [1.0, 2.0]

    def test_historial_limitado_a_1000(self):
        m = MetricsCollector()
        for i in range(1005):
            m.record_latency("lat", float(i))
        assert len(m.metrics_history["lat"]) == 1000
        assert m.metrics_history["lat"][0] == 5.0


class TestRecordError:
    def test_acumula_por_tipo(self):
        m = MetricsCollector()
        m.record_error("reqs", "timeout")
        m.record_error("reqs", "timeout")
        m.record_error("reqs", "conn")
        assert m.metrics["reqs"]["errors"] == {"timeout": 2, "conn": 1}


class TestPrometheusFormat:
    def test_formato_conteos(self):
        m = MetricsCollector()
        m.increment("ollama_request")
        out = m.get_prometheus_format()
        assert "ollama_request_count 1" in out

    def test_formato_latencia(self):
        m = MetricsCollector()
        m.record_latency("ollama_request", 1.2345)
        out = m.get_prometheus_format()
        assert "ollama_request_latency_avg 1.234" in out

    def test_formato_errores(self):
        m = MetricsCollector()
        m.record_error("ollama_request", "timeout")
        out = m.get_prometheus_format()
        assert "ollama_request_error_timeout 1" in out

    def test_vacio(self):
        assert MetricsCollector().get_prometheus_format() == ""

    def test_mezcla_series(self):
        m = MetricsCollector()
        m.increment("a")
        m.record_latency("b", 5.0)
        out = m.get_prometheus_format()
        assert "a_count 1" in out
        assert "b_latency_avg 5.000" in out
