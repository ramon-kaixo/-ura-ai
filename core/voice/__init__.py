"""Shim temporal — voice se ha movido a motor.core.voice."""
import sys
import motor.core.voice
sys.modules[__name__] = motor.core.voice
