"""Shim temporal — constants se ha movido a motor.core.agents.constants."""
import sys
import motor.core.agents.constants
sys.modules[__name__] = motor.core.agents.constants
