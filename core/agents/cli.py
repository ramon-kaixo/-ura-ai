"""Shim temporal — cli se ha movido a motor.core.agents.cli."""
import sys
import motor.core.agents.cli
sys.modules[__name__] = motor.core.agents.cli
