"""Shim temporal — conciencia se ha movido a motor.core.agents.conciencia."""

import sys

import motor.core.agents.conciencia

sys.modules[__name__] = motor.core.agents.conciencia
