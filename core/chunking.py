"""Shim temporal — chunking se ha movido a motor.core.chunking."""
import sys

import motor.core.chunking

sys.modules[__name__] = motor.core.chunking
