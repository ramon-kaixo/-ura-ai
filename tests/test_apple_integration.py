#!/usr/bin/env python3
"""Tests para core/apple_integration.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestAppleScript:
    def test_run_applescript_basic(self):
        from core.apple_integration import run_applescript

        result = run_applescript('return "hello"')
        assert result == "hello"

    def test_run_applescript_math(self):
        from core.apple_integration import run_applescript

        result = run_applescript("return 2 + 2")
        assert result == "4"

    def test_module_imports(self):
        from core.apple_integration import (
            get_calendar_events,
            create_calendar_event,
            create_reminder,
        )

        assert callable(get_calendar_events)
        assert callable(create_calendar_event)
        assert callable(create_reminder)
