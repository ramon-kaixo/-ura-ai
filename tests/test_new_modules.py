#!/usr/bin/env python3
"""Tests para nuevos módulos — LLM Cache + Thread Pool + Conversation Truncator"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLLMCache:
    def test_cache_hit(self):
        from core.llm_cache import LLMCache

        cache = LLMCache(max_size=10, ttl=60)
        cache.set("test", "hello")
        assert cache.get("test") == "hello"

    def test_cache_miss(self):
        from core.llm_cache import LLMCache

        cache = LLMCache(max_size=10, ttl=60)
        assert cache.get("nonexistent") is None

    def test_cache_expiry(self):
        from core.llm_cache import LLMCache

        cache = LLMCache(max_size=10, ttl=1)
        cache.set("test", "hello")
        time.sleep(1.1)
        assert cache.get("test") is None

    def test_cache_stats(self):
        from core.llm_cache import LLMCache

        cache = LLMCache(max_size=10)
        cache.set("a", "1")
        cache.get("a")
        cache.get("b")
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] == 1

    def test_cache_max_size(self):
        from core.llm_cache import LLMCache

        cache = LLMCache(max_size=3)
        for i in range(5):
            cache.set(f"key{i}", f"val{i}")
        assert cache.stats["size"] == 3


class TestThreadPool:
    def test_submit_task(self):
        from core.thread_pool import URAThreadPool

        pool = URAThreadPool(max_workers=2)
        f = pool.submit(lambda x: x * 2, 21)
        assert f.result(timeout=5) == 42
        pool.shutdown()

    def test_multiple_tasks(self):
        from core.thread_pool import URAThreadPool

        pool = URAThreadPool(max_workers=2)
        results = []

        def worker(n):
            time.sleep(0.1)
            return n * n

        futures = [pool.submit(worker, i) for i in range(5)]
        for f in futures:
            results.append(f.result(timeout=5))
        assert results == [0, 1, 4, 9, 16]
        pool.shutdown()


class TestConversationTruncator:
    def test_short_conversation_passes(self):
        from core.conversation_truncator import ConversationTruncator

        ct = ConversationTruncator(max_tokens=5000)
        msgs = [{"role": "user", "content": "Hola"}, {"role": "assistant", "content": "Qué tal"}]
        result = ct.truncate(msgs)
        assert len(result) == 2  # Sin cambios

    def test_long_conversation_truncates(self):
        from core.conversation_truncator import ConversationTruncator

        ct = ConversationTruncator(max_tokens=50)
        msgs = [
            {"role": "user", "content": "Hola " * 100},
            {"role": "assistant", "content": "Adiós " * 100},
        ]
        result = ct.truncate(msgs)
        assert len(result) < len(msgs)  # Debe truncar

    def test_estimate_tokens(self):
        from core.conversation_truncator import ConversationTruncator

        ct = ConversationTruncator()
        assert ct.estimate_tokens("hello world") > 0
        assert ct.estimate_tokens("a" * 400) == 100


class TestConfigManager:
    def test_default_config(self):
        from core.config_manager import ConfigManager

        cm = ConfigManager()
        cm.load()
        assert cm.config.ollama.default_model in ("llama3.2:3b", "qwen3:32b-q8_0")
        assert cm.config.dashboard.port == 5051

    def test_get_by_path(self):
        from core.config_manager import ConfigManager

        cm = ConfigManager()
        cm.load()
        assert cm.get("ollama.default_model") in ("llama3.2:3b", "qwen3:32b-q8_0")
