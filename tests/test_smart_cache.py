#!/usr/bin/env python3
"""
Tests unitarios para SmartCache.
"""

import time
import unittest
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.smart_cache import SmartCache, get_smart_cache


class TestSmartCache(unittest.TestCase):
    def setUp(self):
        """Caché nueva para cada test."""
        self.cache = SmartCache(default_ttl=1)  # TTL de 1 segundo para tests rápidos

    def test_set_and_get(self):
        """Probar set y get básicos."""
        self.cache.set("key1", "value1")
        self.assertEqual(self.cache.get("key1"), "value1")

    def test_get_nonexistent(self):
        """Probar get de clave inexistente."""
        self.assertIsNone(self.cache.get("nonexistent"))

    def test_ttl_expiration(self):
        """Probar expiración por TTL."""
        self.cache.set("key1", "value1", ttl=1)
        self.assertEqual(self.cache.get("key1"), "value1")
        time.sleep(1.1)
        self.assertIsNone(self.cache.get("key1"))

    def test_invalidate_pattern(self):
        """Probar invalidación por patrón."""
        self.cache.set("ura:hola", "value1")
        self.cache.set("ura:mundo", "value2")
        self.cache.set("other:test", "value3")

        self.cache.invalidate("ura:")

        self.assertIsNone(self.cache.get("ura:hola"))
        self.assertIsNone(self.cache.get("ura:mundo"))
        self.assertEqual(self.cache.get("other:test"), "value3")

    def test_clear(self):
        """Probor limpieza completa."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        self.cache.clear()
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_singleton(self):
        """Probar que get_smart_cache devuelve la misma instancia."""
        cache1 = get_smart_cache()
        cache2 = get_smart_cache()
        self.assertIs(cache1, cache2)


if __name__ == "__main__":
    unittest.main()
