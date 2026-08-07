"""Shim temporal — telemetry se ha movido a motor.core.agents.telemetry."""
import sys
import motor.core.agents.telemetry
sys.modules[__name__] = motor.core.agents.telemetry
