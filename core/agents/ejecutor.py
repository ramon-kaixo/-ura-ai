"""Shim temporal — ejecutor se ha movido a motor.core.agents.ejecutor."""
import sys
import motor.core.agents.ejecutor
sys.modules[__name__] = motor.core.agents.ejecutor
