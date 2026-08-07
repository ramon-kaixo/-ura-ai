"""Shim temporal — query_cache se ha movido a motor.core.query_cache."""
import sys
import motor.core.query_cache
sys.modules[__name__] = motor.core.query_cache
