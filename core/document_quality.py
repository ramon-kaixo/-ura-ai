"""Shim temporal — document_quality se ha movido a motor.core.document_quality."""
import sys

import motor.core.document_quality

sys.modules[__name__] = motor.core.document_quality
