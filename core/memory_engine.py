"""Shim temporal — memory_engine se ha movido a motor.core.memory_engine."""
import sys

import motor.core.memory_engine

sys.modules[__name__] = motor.core.memory_engine
