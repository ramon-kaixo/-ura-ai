#!/usr/bin/env python3
"""
Tests unitarios para URAThreadPool.
"""

import time
import unittest
import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.thread_pool import URAThreadPool, get_thread_pool


class TestURAThreadPool(unittest.TestCase):
    def setUp(self):
        """Pool nuevo para cada test."""
        self.pool = URAThreadPool(max_workers=2)

    def tearDown(self):
        """Cerrar pool después de cada test."""
        self.pool.shutdown(wait=False)

    def test_submit_simple_task(self):
        """Probar envío de tarea simple."""

        def simple_task(x):
            return x * 2

        future = self.pool.submit(simple_task, 5)
        result = future.result(timeout=5)
        self.assertEqual(result, 10)

    def test_submit_multiple_tasks(self):
        """Probar envío de múltiples tareas."""

        def task(x):
            time.sleep(0.1)
            return x * 2

        futures = [self.pool.submit(task, i) for i in range(5)]
        results = [f.result(timeout=5) for f in futures]
        self.assertEqual(results, [0, 2, 4, 6, 8])

    def test_cleanup_finished(self):
        """Probar limpieza de futures terminados (stats)."""

        def quick_task(x):
            return x

        futures = [self.pool.submit(quick_task, i) for i in range(5)]

        # Esperar a que terminen
        for f in futures:
            f.result(timeout=5)

        # Verificar stats
        stats = self.pool.stats
        self.assertIn("workers", stats)
        self.assertIn("active", stats)

    def test_shutdown(self):
        """Probar cierre del pool."""
        self.pool.shutdown(wait=True)

        # Intentar enviar tarea después de shutdown debería fallar
        def task():
            return "test"

        try:
            future = self.pool.submit(task)
            future.result(timeout=1)
            self.fail("Debería haber fallado después de shutdown")
        except:
            pass  # Esperado

    def test_singleton(self):
        """Probar que get_thread_pool devuelve la misma instancia."""
        pool1 = get_thread_pool()
        pool2 = get_thread_pool()
        self.assertIs(pool1, pool2)


if __name__ == "__main__":
    unittest.main()
