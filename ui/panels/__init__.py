#!/usr/bin/env python3
"""
URA - UI Panels Package
Paneles de la interfaz optimizada
"""

from ui.panels.header import create_compact_header
from ui.panels.input_bar import create_compact_input_bar
from ui.panels.ura_panel import create_ura_panel_optimized
from ui.panels.viewer_panel import create_viewer_panel
from ui.panels.windsurf_panel import create_windsurf_panel_optimized

__all__ = [
    "create_compact_header",
    "create_compact_input_bar",
    "create_ura_panel_optimized",
    "create_viewer_panel",
    "create_windsurf_panel_optimized",
]
