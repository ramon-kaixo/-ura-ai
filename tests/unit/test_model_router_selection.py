"""Tests for core/model_router/model_selection.py."""

from unittest.mock import patch

import pytest

from core.model_router import model_selection as ms


@pytest.fixture(autouse=True)
def limpiar_estado():
    ms.success_rates.clear()
    yield
    ms.success_rates.clear()


class TestClasificarPeticion:
    @pytest.mark.unit
    def test_vacio_devuelve_default(self):
        assert ms.clasificar_peticion([]) == ms.DEFAULT_TIPO

    @pytest.mark.unit
    def test_no_matches_devuelve_default(self):
        assert ms.clasificar_peticion([{"content": "hola que tal"}]) == ms.DEFAULT_TIPO

    @pytest.mark.unit
    def test_codigo_rapido(self):
        assert ms.clasificar_peticion([{"content": "hay un bug, haz un fix del script"}]) == "codigo_rapido"

    @pytest.mark.unit
    def test_razonamiento(self):
        assert ms.clasificar_peticion([{"content": "analizar y evaluar la estrategia"}]) == "razonamiento"

    @pytest.mark.unit
    def test_codigo_complejo(self):
        assert ms.clasificar_peticion([{"content": "revisar codigo y optimizar codigo"}]) == "codigo_complejo"

    @pytest.mark.unit
    def test_vision(self):
        assert ms.clasificar_peticion([{"content": "analizar imagen del grafico"}]) == "vision"

    @pytest.mark.unit
    def test_embeddings(self):
        assert ms.clasificar_peticion([{"content": "buscar semantico del vector"}]) == "embeddings"

    @pytest.mark.unit
    def test_respuesta_rapida(self):
        assert ms.clasificar_peticion([{"content": "que es un lambda y definirlo"}]) == "respuesta_rapida"

    @pytest.mark.unit
    def test_multiple_messages(self):
        msgs = [{"content": "hola"}, {"content": "fix del bug"}]
        assert ms.clasificar_peticion(msgs) == "codigo_rapido"

    @pytest.mark.unit
    def test_content_no_str_ignorado(self):
        assert ms.clasificar_peticion([{"content": 42}]) == ms.DEFAULT_TIPO

    @pytest.mark.unit
    def test_mayusculas_normalizadas(self):
        assert ms.clasificar_peticion([{"content": "FIX del BUG"}]) == "codigo_rapido"


class TestObtenerModelosDisponibles:
    @pytest.mark.unit
    def test_ok(self):
        with patch("urllib.request.urlopen") as mock_open:
            resp = mock_open.return_value.__enter__.return_value
            resp.read.return_value = b'{"models": [{"name": "qwen3.6:27b"}, {"name": "llama3:latest"}]}'
            assert ms.obtener_modelos_disponibles("http://fake:1") == {"qwen3.6:27b", "llama3:latest"}

    @pytest.mark.unit
    def test_error_devuelve_vacio(self):
        with patch("urllib.request.urlopen", side_effect=OSError("conn")):
            assert ms.obtener_modelos_disponibles("http://fake:1") == set()


class TestGetModelParams:
    @pytest.mark.unit
    def test_exacto(self):
        p = ms._get_model_params("qwen3-coder:30b")
        assert p["temperature"] == 0.1
        assert p["num_predict"] == 8192

    @pytest.mark.unit
    def test_por_prefijo_base(self):
        p = ms._get_model_params("qwen3-coder:30b-instruct")
        assert p["temperature"] == 0.1

    @pytest.mark.unit
    def test_desconocido_defaults(self):
        p = ms._get_model_params("otro:modelo")
        assert p == ms.DEFAULT_MODEL_PARAMS
        p["temperature"] = 99.0
        assert ms.DEFAULT_MODEL_PARAMS["temperature"] == 0.2


class TestApplyModelParams:
    @pytest.mark.unit
    def test_anade_options(self):
        data = {}
        out = ms._apply_model_params(data, "llama3:latest")
        assert "options" in out
        assert out["options"]["temperature"] == 0.2

    @pytest.mark.unit
    def test_no_sobreescribe_opciones_existentes(self):
        data = {"options": {"temperature": 1.0}}
        out = ms._apply_model_params(data, "llama3:latest")
        assert out["options"]["temperature"] == 1.0

    @pytest.mark.unit
    def test_mutacion_directa(self):
        data = {}
        ms._apply_model_params(data, "llama3:latest")
        assert data["options"]["num_predict"] == 4096


class TestSuccessRates:
    @pytest.mark.unit
    def test_record_y_get(self):
        ms._record_success("m1", "t1", ok=True)
        ms._record_success("m1", "t1", ok=False)
        assert ms._get_success_rate("m1", "t1") == 0.5

    @pytest.mark.unit
    def test_sin_datos_default_05(self):
        assert ms._get_success_rate("nada", "t1") == 0.5

    @pytest.mark.unit
    def test_100_exitos(self):
        ms._record_success("m2", "t2", ok=True)
        assert ms._get_success_rate("m2", "t2") == 1.0

    @pytest.mark.unit
    def test_tipos_separados(self):
        ms._record_success("m3", "a", ok=True)
        assert ms._get_success_rate("m3", "b") == 0.5


class TestSeleccionarModelo:
    @pytest.mark.unit
    def test_modelo_exacto_disponible(self):
        assert ms.seleccionar_modelo("respuesta_rapida", {"qwen3.6:27b"}) == "qwen3.6:27b"

    @pytest.mark.unit
    def test_prioriza_tasa_exito(self):
        ms._record_success("qwen3.6:27b", "respuesta_rapida", ok=True)
        assert ms.seleccionar_modelo("respuesta_rapida", {"llama3.3:70b", "qwen3.6:27b"}) == "qwen3.6:27b"

    @pytest.mark.unit
    def test_match_por_base(self):
        assert ms.seleccionar_modelo("codigo_rapido", {"qwen3-coder:30b-instruct"}) == "qwen3-coder:30b-instruct"

    @pytest.mark.unit
    def test_fallback_cuando_ninguno(self):
        with patch("core.model_router.metrics.metrics") as mock_metrics:
            result = ms.seleccionar_modelo("razonamiento", {"llama3:latest"})
        assert result == "llama3:latest"
        mock_metrics.increment.assert_called_once()

    @pytest.mark.unit
    def test_primero_disponible(self):
        result = ms.seleccionar_modelo("vision", {"llava:7b"})
        assert result == "llava:7b"

    @pytest.mark.unit
    def test_sin_disponibles_devuelve_primero_de_ruta(self):
        assert ms.seleccionar_modelo("razonamiento", set()) == "qwen3.6:27b"

    @pytest.mark.unit
    def test_tipo_desconocido_usa_default(self):
        assert ms.seleccionar_modelo("tipo_inexistente", {"qwen3.6:27b", "llama3.3:70b"}) in {
            "qwen3.6:27b",
            "llama3.3:70b",
        }

    @pytest.mark.unit
    def test_evita_duplicados_por_base(self):
        result = ms.seleccionar_modelo("codigo_rapido", {"qwen3-coder:30b-q8_0", "qwen3-coder:30b"})
        assert result in {"qwen3-coder:30b-q8_0", "qwen3-coder:30b"}

    @pytest.mark.unit
    def test_fallback_sin_metrics_desde_inicio(self):
        original = ms._get_success_rate
        try:
            ms._get_success_rate = lambda m, t: 0.5
            ms.seleccionar_modelo("respuesta_rapida", {"llama3.3:70b"})
        finally:
            ms._get_success_rate = original
