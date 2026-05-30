#!/usr/bin/env python3
"""
Smoke Test: Redis + Slack Idempotency
Verifica que la idempotencia está funcionando correctamente con Slack
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.idempotency import REDIS_AVAILABLE, idempotency_manager
from core.slack_integration import IDEMPOTENCY_AVAILABLE, SlackClient


def test_slack_idempotency():
    """Probar idempotencia con Slack"""
    print("=== Smoke Test: Redis + Slack Idempotency ===\n")

    print(f"Redis Available: {REDIS_AVAILABLE}")
    print(f"Idempotency Available in Slack: {IDEMPOTENCY_AVAILABLE}")
    print()

    # Crear cliente Slack (sin webhook real para test)
    slack_client = SlackClient(webhook_url=None)

    # Test 1: Primer envío (debería intentar enviar)
    print("1. Primer envío (sin webhook real)...")
    result1 = slack_client.send_message(
        channel="#test", text="Test message 1 - First attempt", use_idempotency=True
    )
    print(f"   Result: {result1}")
    print()

    # Test 2: Segundo envío con mismo mensaje (debería detectar duplicado)
    print("2. Segundo envío con mismo mensaje (debería detectar duplicado)...")
    result2 = slack_client.send_message(
        channel="#test", text="Test message 1 - First attempt", use_idempotency=True
    )
    print(f"   Result: {result2}")
    print()

    # Verificar si detectó duplicado
    if result2.get("status") == "already_sent":
        print("   ✓ Idempotencia funcionó: Detectó mensaje duplicado")
    else:
        print("   ✗ Idempotencia NO funcionó: No detectó duplicado")
    print()

    # Test 3: Mensaje diferente (debería intentar enviar)
    print("3. Tercer envío con mensaje diferente...")
    result3 = slack_client.send_message(
        channel="#test", text="Test message 2 - Different message", use_idempotency=True
    )
    print(f"   Result: {result3}")
    print()

    # Test 4: Verificar Redis
    print("4. Verificando Redis...")
    stats = idempotency_manager.store.get_stats()
    print(f"   Redis Stats: {stats}")
    print()

    # Test 5: Invalidar claves
    print("5. Invalidando claves de prueba...")
    idempotency_manager.invalidate(
        "slack_send_message", {"channel": "#test", "text": "Test message 1 - First attempt"}
    )
    idempotency_manager.invalidate(
        "slack_send_message", {"channel": "#test", "text": "Test message 2 - Different message"}
    )
    print("   ✓ Claves invalidadas")
    print()

    print("=== Smoke Test Completado ===")


if __name__ == "__main__":
    test_slack_idempotency()
