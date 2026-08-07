"""Shim temporal — search_engine se ha movido a motor.core.search_engine."""
import sys

import motor.core.search_engine

sys.modules[__name__] = motor.core.search_engine
