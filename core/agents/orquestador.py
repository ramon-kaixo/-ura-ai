"""Shim temporal — orquestador se ha movido a motor.core.agents.orquestador."""

import sys

import motor.core.agents.orquestador

sys.modules[__name__] = motor.core.agents.orquestador
