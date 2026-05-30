"""Tests for ui/panels/ — UI panel creation functions.

PyQt5 widgets cannot be instantiated in test environment (segfault).
We verify imports and callable signatures only.
"""


class TestHeaderPanel:
    """ui/panels/header.py — compact header bar."""

    def test_imports_without_error(self):
        from ui.panels.header import create_compact_header

        assert callable(create_compact_header)


class TestInputBar:
    """ui/panels/input_bar.py — compact input bar."""

    def test_imports_without_error(self):
        from ui.panels.input_bar import create_compact_input_bar

        assert callable(create_compact_input_bar)


class TestUraPanel:
    """ui/panels/ura_panel.py — main URA chat panel."""

    def test_imports_without_error(self):
        from ui.panels.ura_panel import create_ura_panel_optimized

        assert callable(create_ura_panel_optimized)


class TestViewerPanel:
    """ui/panels/viewer_panel.py — data viewer panel."""

    def test_imports_without_error(self):
        from ui.panels.viewer_panel import create_viewer_panel

        assert callable(create_viewer_panel)


class TestWindsurfPanel:
    """ui/panels/windsurf_panel.py — Windsurf IDE panel."""

    def test_imports_without_error(self):
        from ui.panels.windsurf_panel import create_windsurf_panel_optimized

        assert callable(create_windsurf_panel_optimized)


class TestPanelsPackage:
    """ui/panels/__init__.py — package exports."""

    def test_all_exports_defined(self):
        from ui.panels import __all__

        expected = [
            "create_compact_header",
            "create_compact_input_bar",
            "create_ura_panel_optimized",
            "create_viewer_panel",
            "create_windsurf_panel_optimized",
        ]
        for name in expected:
            assert name in __all__, f"Missing: {name}"

    def test_all_exports_are_callable(self):
        import ui.panels as pkg

        for name in pkg.__all__:
            obj = getattr(pkg, name)
            assert callable(obj), f"Not callable: {name}"
