"""Tests for core/mochila/rate_limiter.py."""

from unittest.mock import patch

from core.mochila.rate_limiter import RateLimiter


class TestLimite:
    def test_default_30(self):
        rl = RateLimiter()
        assert rl._limite("ollama") == 30

    def test_configurado(self):
        rl = RateLimiter()
        rl.configurar("ollama", 5)
        assert rl._limite("ollama") == 5

    def test_config_por_provider_independiente(self):
        rl = RateLimiter()
        rl.configurar("ollama", 5)
        assert rl._limite("gemini") == 30


class TestPuedePasar:
    def test_vacio_puede(self):
        rl = RateLimiter()
        puede, actual, limite = rl.puede_pasar("ollama")
        assert puede is True
        assert actual == 0
        assert limite == 30

    def test_bajo_limite_puede(self):
        rl = RateLimiter()
        rl.configurar("ollama", 2)
        rl.registrar("ollama")
        puede, actual, _ = rl.puede_pasar("ollama")
        assert puede is True
        assert actual == 1

    def test_alcanza_limite_bloquea(self):
        rl = RateLimiter()
        rl.configurar("ollama", 2)
        rl.registrar("ollama")
        rl.registrar("ollama")
        puede, actual, _ = rl.puede_pasar("ollama")
        assert puede is False
        assert actual == 2

    def test_expira_ventana(self):
        rl = RateLimiter()
        rl.configurar("ollama", 1)
        rl.registrar("ollama")
        with patch("core.mochila.rate_limiter.time.time", return_value=1000.0):
            rl._ventanas["ollama"] = [100.0]  # fuera de la ventana de 60s
            puede, actual, _ = rl.puede_pasar("ollama")
        assert puede is True
        assert actual == 0

    def test_providers_independientes(self):
        rl = RateLimiter()
        rl.configurar("a", 1)
        rl.registrar("a")
        puede, _, _ = rl.puede_pasar("b")
        assert puede is True


class TestRegistrar:
    def test_incrementa_ventana(self):
        rl = RateLimiter()
        rl.registrar("ollama")
        assert len(rl._ventanas["ollama"]) == 1

    def test_registros_multiples(self):
        rl = RateLimiter()
        rl.registrar("ollama")
        rl.registrar("ollama")
        assert len(rl._ventanas["ollama"]) == 2


class TestEstado:
    def test_estructura(self):
        rl = RateLimiter()
        rl.configurar("ollama", 7)
        st = rl.estado("ollama")
        assert st["provider"] == "ollama"
        assert st["can_pass"] is True
        assert st["max_requests"] == 7
        assert st["window_seconds"] == 60

    def test_estado_refleja_bloqueo(self):
        rl = RateLimiter()
        rl.configurar("ollama", 1)
        rl.registrar("ollama")
        assert rl.estado("ollama")["can_pass"] is False


class TestCargarConfig:
    def test_config_existente(self, tmp_path, monkeypatch):
        cfg = tmp_path / "limits.json"
        cfg.write_text('{"ollama": 3, "gemini": 7}')
        rl = RateLimiter()
        rl._cargar_config(str(cfg))
        assert rl._limite("ollama") == 3
        assert rl._limite("gemini") == 7

    def test_ignora_no_ints(self, tmp_path):
        cfg = tmp_path / "limits.json"
        cfg.write_text('{"ollama": "abc"}')
        rl = RateLimiter()
        rl._cargar_config(str(cfg))
        assert rl._limite("ollama") == 30

    def test_archivo_inexistente_no_rompe(self, tmp_path):
        rl = RateLimiter()
        rl._cargar_config(str(tmp_path / "nope.json"))
        assert rl._limite("ollama") == 30

    def test_json_roto_no_rompe(self, tmp_path):
        cfg = tmp_path / "limits.json"
        cfg.write_text("{mal")
        rl = RateLimiter()
        rl._cargar_config(str(cfg))
        assert rl._limite("ollama") == 30
