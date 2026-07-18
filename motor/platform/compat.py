"""CompatibilityChecker — forward/backward compatibility rules."""

from __future__ import annotations


def _parse_major_minor(version: str) -> tuple[int, int]:
    parts = version.split(".")
    return int(parts[0]), int(parts[1])


class CompatibilityChecker:
    """Checks compatibility between two protocol versions."""

    @staticmethod
    def is_backward_compatible(emitter: str, receiver: str) -> bool:
        """New receiver must understand old emitter messages."""
        em_maj, em_min = _parse_major_minor(emitter)
        rc_maj, rc_min = _parse_major_minor(receiver)
        if em_maj != rc_maj:
            return False
        return em_min <= rc_min

    @staticmethod
    def is_forward_compatible(emitter: str, receiver: str) -> bool:
        """Old receiver must understand new emitter messages."""
        em_maj, em_min = _parse_major_minor(emitter)
        rc_maj, rc_min = _parse_major_minor(receiver)
        if em_maj != rc_maj:
            return False
        return rc_min <= em_min

    @staticmethod
    def can_communicate(emitter: str, receiver: str) -> bool:
        """Same MAJOR = can communicate (MINOR differences are fine)."""
        em_maj, _ = _parse_major_minor(emitter)
        rc_maj, _ = _parse_major_minor(receiver)
        return em_maj == rc_maj
