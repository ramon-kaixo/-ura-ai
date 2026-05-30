#!/usr/bin/env python3
"""
Test Redis Idempotency - Prueba de idempotencia con Redis
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.idempotency import REDIS_AVAILABLE, idempotency_manager


def test_redis_idempotency():
    """Probar idempotencia con Redis"""
    print("Testing Redis Idempotency...")
    print(f"Redis Available: {REDIS_AVAILABLE}")

    # Test 1: Crear y recuperar clave
    print("\n1. Testing create and retrieve...")

    def expensive_operation():
        return {"result": "success", "data": "test_data"}

    result1 = idempotency_manager.execute_or_retrieve(
        "test_operation", {"param": "value"}, expensive_operation, ttl_seconds=60
    )
    print(f"First call result: {result1}")

    # Test 2: Recuperar desde caché
    print("\n2. Testing retrieve from cache...")
    result2 = idempotency_manager.execute_or_retrieve(
        "test_operation", {"param": "value"}, expensive_operation, ttl_seconds=60
    )
    print(f"Second call result (should be cached): {result2}")

    # Test 3: Verificar si es el mismo resultado
    print("\n3. Verifying results are identical...")
    print(f"Results match: {result1 == result2}")

    # Test 4: Invalidar clave
    print("\n4. Testing invalidation...")
    idempotency_manager.invalidate("test_operation", {"param": "value"})
    print("Key invalidated")

    # Test 5: Recuperar después de invalidación
    print("\n5. Testing retrieve after invalidation...")
    result3 = idempotency_manager.execute_or_retrieve(
        "test_operation", {"param": "value"}, expensive_operation, ttl_seconds=60
    )
    print(f"Third call result (should be fresh): {result3}")

    # Test 6: Verificar estadísticas
    print("\n6. Getting statistics...")
    stats = idempotency_manager.store.get_stats()
    print(f"Store stats: {stats}")

    print("\n✓ All tests completed successfully!")


if __name__ == "__main__":
    test_redis_idempotency()
