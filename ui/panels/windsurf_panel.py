#!/usr/bin/env python3
"""
URA - Windsurf Panel
Panel de respuestas de Windsurf optimizado
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QLabel, QToolButton, QTextEdit, QVBoxLayout


def create_windsurf_panel_optimized(context, parent_layout):
    """
    Crear panel Windsurf optimizado - 100% altura, con toolbar colapsable

    Args:
        context: Contexto de la ventana principal (self)
        parent_layout: Layout padre donde agregar el panel
    """
    context.windsurf_panel = QGroupBox()
    context.windsurf_panel.setStyleSheet("""
        QGroupBox {
            border: none;
            margin: 0px;
            padding: 0px;
        }
    """)

    windsurf_layout = QVBoxLayout(context.windsurf_panel)
    windsurf_layout.setContentsMargins(0, 0, 0, 0)
    windsurf_layout.setSpacing(2)

    # TOOLBAR superior con título y botón colapsar
    toolbar = context.windsurf_panel
    toolbar.setFixedHeight(28)
    toolbar.setStyleSheet("background-color: #2a2a2a; border-bottom: 1px solid #444;")
    toolbar_layout = QHBoxLayout(toolbar)
    toolbar_layout.setContentsMargins(8, 0, 4, 0)
    toolbar_layout.setSpacing(4)

    title = QLabel("Respuestas de Windsurf")
    title.setStyleSheet("color: #e0e0e0; font-size: 12px; font-weight: 600;")
    toolbar_layout.addWidget(title)
    toolbar_layout.addStretch()

    context.windsurf_collapse_btn = QToolButton()
    context.windsurf_collapse_btn.setText("⬅")
    context.windsurf_collapse_btn.setToolTip("Colapsar panel de Windsurf")
    context.windsurf_collapse_btn.setCursor(Qt.PointingHandCursor)
    context.windsurf_collapse_btn.setStyleSheet("""
        QToolButton {
            background-color: transparent;
            color: #a0a0a0;
            border: none;
            font-size: 14px;
            padding: 2px 8px;
        }
        QToolButton:hover { color: #007bff; background-color: #3a3a3a; border-radius: 3px; }
    """)
    context.windsurf_collapse_btn.clicked.connect(context.toggle_windsurf_panel)
    toolbar_layout.addWidget(context.windsurf_collapse_btn)

    windsurf_layout.addWidget(toolbar)

    # Área de respuestas de Windsurf (fondo claro, mensajes coloreados por emisor)
    context.windsurf_response_text = QTextEdit()
    context.windsurf_response_text.setStyleSheet("""
        QTextEdit {
            background-color: #fafafa;
            color: #222222;
            border: 1px solid #cccccc;
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 13px;
        }
    """)
    context.windsurf_response_text.setReadOnly(True)
    context.windsurf_response_text.setPlaceholderText("Respuestas de Windsurf aparecerán aquí...")
    windsurf_layout.addWidget(context.windsurf_response_text)

    parent_layout.addWidget(context.windsurf_panel)
