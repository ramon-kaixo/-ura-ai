"""Shim temporal — json_logger se ha movido a motor.core.json_logger."""

import sys

import motor.core.json_logger

sys.modules[__name__] = motor.core.json_logger
