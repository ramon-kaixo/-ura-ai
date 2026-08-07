"""Shim temporal — reparador se ha movido a motor.core.agents.reparador."""
import sys
import motor.core.agents.reparador
sys.modules[__name__] = motor.core.agents.reparador
