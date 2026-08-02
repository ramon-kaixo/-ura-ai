"""Tests for scripts/pro/router_rate_limiter.py."""
import time

from scripts.pro.router_rate_limiter import RateLimiter


class TestRateLimiter:
    def test_init_defaults(self):
        rl = RateLimiter()
        assert rl.max_requests == 100
        assert rl.window_seconds == 60

    def test_init_custom(self):
        rl = RateLimiter(max_requests=5, window_seconds=10)
        assert rl.max_requests == 5
        assert rl.window_seconds == 10

    def test_is_allowed_under_limit(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert rl.is_allowed("1.2.3.4") is True
        assert rl.is_allowed("1.2.3.4") is True
        assert rl.is_allowed("1.2.3.4") is True

    def test_is_allowed_at_limit(self):
        rl = RateLimiter(max_requests=2, window_seconds=60)
        rl.is_allowed("1.2.3.4")
        rl.is_allowed("1.2.3.4")
        assert rl.is_allowed("1.2.3.4") is False

    def test_is_allowed_different_ips(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        assert rl.is_allowed("1.2.3.4") is True
        assert rl.is_allowed("5.6.7.8") is True
        # Ahora ambos están en su límite
        assert rl.is_allowed("1.2.3.4") is False
        assert rl.is_allowed("5.6.7.8") is False

    def test_window_expires(self):
        rl = RateLimiter(max_requests=1, window_seconds=0)
        assert rl.is_allowed("1.2.3.4") is True
        # Esperamos un poco para que la ventana expire
        time.sleep(0.1)
        assert rl.is_allowed("1.2.3.4") is True

    def test_get_remaining(self):
        rl = RateLimiter(max_requests=3, window_seconds=60)
        assert rl.get_remaining("1.2.3.4") == 3
        rl.is_allowed("1.2.3.4")
        assert rl.get_remaining("1.2.3.4") == 2
        rl.is_allowed("1.2.3.4")
        rl.is_allowed("1.2.3.4")
        assert rl.get_remaining("1.2.3.4") == 0

    def test_get_remaining_never_negative(self):
        rl = RateLimiter(max_requests=1, window_seconds=60)
        rl.is_allowed("1.2.3.4")
        rl.is_allowed("1.2.3.4")  # Rechazado, pero intentamos
        assert rl.get_remaining("1.2.3.4") == 0
