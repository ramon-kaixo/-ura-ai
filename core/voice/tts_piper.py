"""Shim temporal."""
import sys
import motor.core.voice.tts_piper
sys.modules[__name__] = motor.core.voice.tts_piper
