"""Shim temporal — config_manager se ha movido a motor.core.config_manager."""
import sys
import motor.core.config_manager
sys.modules[__name__] = motor.core.config_manager
