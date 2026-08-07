"""Shim temporal — healing se ha movido a motor.core.agents.healing."""
import sys
import motor.core.agents.healing
sys.modules[__name__] = motor.core.agents.healing
