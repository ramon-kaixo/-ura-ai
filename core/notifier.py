"""Shim temporal — notifier se ha movido a motor.core.notifier."""
import sys
import motor.core.notifier
sys.modules[__name__] = motor.core.notifier
