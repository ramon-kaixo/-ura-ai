"""Shim temporal."""

import sys

import motor.core.voice.anker_pipeline

sys.modules[__name__] = motor.core.voice.anker_pipeline
