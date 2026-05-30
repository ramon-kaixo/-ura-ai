#!/usr/bin/env python3
"""
Tests para TrainingGatekeeper.

Pruebas:
- Test 1: should_activate con >500 semillas
- Test 2: should_activate con >7 días
- Test 3: should_activate con condiciones insuficientes
- Test 4: activate_if_ready cuando no debe activar
- Test 5: get_status devuelve estructura correcta
"""

import json
import sys
from datetime import datetime, timedelta
from unittest.mock import patch

sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")

from core.training_gatekeeper import TrainingGatekeeper, TRAINING_STATE_PATH


def test_1_volume_threshold_exceeded():
    """Test 1: should_activate con >500 semillas."""
    print("\n=== Test 1: Umbral de semillas superado ===")

    # Mock pending_seeds_count directamente para devolver 600 semillas
    with patch.object(TrainingGatekeeper, "pending_seeds_count", return_value=600):
        gatekeeper = TrainingGatekeeper(volume_threshold=500)

        should = gatekeeper.should_activate()
        print(f"should_activate: {should}")
        assert should is True, "should_activate debería ser True cuando semillas >= umbral"
        print("✅ Test 1 passed")


def test_2_time_threshold_exceeded():
    """Test 2: should_activate con >7 días."""
    print("\n=== Test 2: Umbral de tiempo superado ===")

    # Simular última activación hace 10 días
    old_date = datetime.now() - timedelta(days=10)
    state = {"last_training": old_date.isoformat()}

    # Escribir estado falso
    TRAINING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

    # Mock pending_seeds_count para devolver pocas semillas
    with patch.object(TrainingGatekeeper, "pending_seeds_count", return_value=10):
        gatekeeper = TrainingGatekeeper(volume_threshold=500, time_threshold_days=7)

        should = gatekeeper.should_activate()
        print(f"should_activate: {should}")
        assert should is True, "should_activate debería ser True cuando días >= umbral"
        print("✅ Test 2 passed")


def test_3_conditions_not_met():
    """Test 3: should_activate con condiciones insuficientes."""
    print("\n=== Test 3: Condiciones no cumplidas ===")

    # Simular última activación hace 2 días
    recent_date = datetime.now() - timedelta(days=2)
    state = {"last_training": recent_date.isoformat()}

    # Escribir estado falso
    TRAINING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

    # Mock pending_seeds_count para devolver pocas semillas
    with patch.object(TrainingGatekeeper, "pending_seeds_count", return_value=10):
        gatekeeper = TrainingGatekeeper(volume_threshold=500, time_threshold_days=7)

        should = gatekeeper.should_activate()
        print(f"should_activate: {should}")
        assert should is False, "should_activate debería ser False cuando condiciones no cumplidas"
        print("✅ Test 3 passed")


def test_4_activate_if_ready_not_activate():
    """Test 4: activate_if_ready cuando no debe activar."""
    print("\n=== Test 4: activate_if_ready cuando no debe activar ===")

    # Simular última activación hace 2 días
    recent_date = datetime.now() - timedelta(days=2)
    state = {"last_training": recent_date.isoformat()}

    # Escribir estado falso
    TRAINING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(TRAINING_STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f)

    # Mock pending_seeds_count para devolver pocas semillas
    with patch.object(TrainingGatekeeper, "pending_seeds_count", return_value=10):
        gatekeeper = TrainingGatekeeper(volume_threshold=500, time_threshold_days=7)

        result = gatekeeper.activate_if_ready()
        print(f"activate_if_ready result: {result}")
        assert result["activated"] is False, "activate_if_ready debería retornar activated=False"
        assert "reason" in result, "result debería tener 'reason'"
        print("✅ Test 4 passed")


def test_5_get_status():
    """Test 5: get_status devuelve estructura correcta."""
    print("\n=== Test 5: get_status devuelve estructura correcta ===")

    # Mock pending_seeds_count para devolver 100 semillas pendientes
    with patch.object(TrainingGatekeeper, "pending_seeds_count", return_value=100):
        # Simular última activación hace 3 días
        recent_date = datetime.now() - timedelta(days=3)
        state = {"last_training": recent_date.isoformat()}

        TRAINING_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(TRAINING_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(state, f)

        gatekeeper = TrainingGatekeeper(volume_threshold=500, time_threshold_days=7)

        status = gatekeeper.get_status()
        print(f"get_status result: {json.dumps(status, indent=2)}")

        assert "pending_seeds" in status, "status debería tener 'pending_seeds'"
        assert "days_since_last" in status, "status debería tener 'days_since_last'"
        assert "threshold_volume" in status, "status debería tener 'threshold_volume'"
        assert "threshold_time" in status, "status debería tener 'threshold_time'"
        assert "will_activate_on_next_check" in status, (
            "status debería tener 'will_activate_on_next_check'"
        )
        assert status["pending_seeds"] == 100, "pending_seeds debería ser 100"
        assert status["days_since_last"] == 3, "days_since_last debería ser 3"
        assert status["threshold_volume"] == 500, "threshold_volume debería ser 500"
        assert status["threshold_time"] == 7, "threshold_time debería ser 7"
        assert status["will_activate_on_next_check"] is False, (
            "will_activate_on_next_check debería ser False"
        )

        print("✅ Test 5 passed")


if __name__ == "__main__":
    print("\n=== Tests de TrainingGatekeeper ===\n")

    test_1_volume_threshold_exceeded()
    test_2_time_threshold_exceeded()
    test_3_conditions_not_met()
    test_4_activate_if_ready_not_activate()
    test_5_get_status()

    print("\n=== Todos los tests completados ===\n")
