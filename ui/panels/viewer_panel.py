#!/usr/bin/env python3
"""
URA - Viewer Panel
Panel lateral de visor (PDF/Web) - oculto por defecto
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

WEBENGINE_AVAILABLE = False
try:
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    WEBENGINE_AVAILABLE = True
except ImportError:
    pass


def create_viewer_panel(context, parent_layout):
    """
    Crear panel lateral de visor (PDF/Web) - oculto por defecto

    Args:
        context: Contexto de la ventana principal (self)
        parent_layout: Layout padre donde agregar el panel
    """
    context.viewer_panel = QGroupBox()
    context.viewer_panel.setStyleSheet("""
        QGroupBox { border: none; margin: 0px; padding: 0px; }
    """)
    viewer_layout = QVBoxLayout(context.viewer_panel)
    viewer_layout.setContentsMargins(0, 0, 0, 0)
    viewer_layout.setSpacing(2)

    # Toolbar del visor
    vtoolbar = QWidget()
    vtoolbar.setFixedHeight(32)
    vtoolbar.setStyleSheet("background-color: #2a2a2a; border-bottom: 1px solid #444;")
    vt_layout = QHBoxLayout(vtoolbar)
    vt_layout.setContentsMargins(8, 0, 4, 0)
    vt_layout.setSpacing(6)

    context.viewer_title = QLabel("Visor")
    context.viewer_title.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: 600;")
    vt_layout.addWidget(context.viewer_title)
    vt_layout.addStretch()

    # Input URL rápido
    context.viewer_url_input = QLineEdit()
    context.viewer_url_input.setPlaceholderText("https://...")
    context.viewer_url_input.setFixedWidth(240)
    context.viewer_url_input.setStyleSheet(
        "QLineEdit { background-color: #1e1e1e; color: #e0e0e0; border: 1px solid #444;"
        " padding: 3px 6px; border-radius: 3px; font-size: 12px; }"
    )
    context.viewer_url_input.returnPressed.connect(context._load_url_from_input)
    vt_layout.addWidget(context.viewer_url_input)

    load_btn = QToolButton()
    load_btn.setText("Ir")
    load_btn.setStyleSheet(
        "QToolButton { color: #e0e0e0; background: #007bff; border: none;"
        " padding: 3px 10px; border-radius: 3px; font-size: 12px; }"
        "QToolButton:hover { background: #0056b3; }"
    )
    load_btn.clicked.connect(context._load_url_from_input)
    vt_layout.addWidget(load_btn)

    close_btn = QToolButton()
    close_btn.setText("✕")
    close_btn.setToolTip("Cerrar visor")
    close_btn.setCursor(Qt.PointingHandCursor)
    close_btn.setStyleSheet(
        "QToolButton { color: #a0a0a0; background: transparent; border: none;"
        " padding: 2px 8px; font-size: 14px; }"
        "QToolButton:hover { color: #dc3545; }"
    )
    close_btn.clicked.connect(context.hide_viewer)
    vt_layout.addWidget(close_btn)

    viewer_layout.addWidget(vtoolbar)

    # Contenido: stacked entre WebEngineView y mensaje de estado
    context.viewer_stack = QStackedWidget()
    if WEBENGINE_AVAILABLE:
        context.web_view = QWebEngineView()
        context.viewer_stack.addWidget(context.web_view)
    else:
        fallback = QLabel("QWebEngineView no disponible. Instala PyQtWebEngine.")
        fallback.setAlignment(Qt.AlignCenter)
        fallback.setStyleSheet("color: #ff6b6b; font-size: 13px; padding: 20px;")
        context.web_view = None
        context.viewer_stack.addWidget(fallback)

    viewer_layout.addWidget(context.viewer_stack)
    parent_layout.addWidget(context.viewer_panel)
