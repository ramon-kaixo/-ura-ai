#!/usr/bin/env python3
"""
Window Setup - Paso 3A
──────────────────────
Configuración de ventana principal y UI.
"""

import logging
from pathlib import Path

from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QFrame,
)

logger = logging.getLogger(__name__)


def setup_window(window, title: str = "URA - Centro de Comando"):
    """
    Configurar ventana principal - Anclada en borde izquierdo.

    Args:
        window: Instancia de ventana PyQt5
        title: Título de la ventana
    """
    window.setWindowTitle(title)

    # Anclar ventana en borde izquierdo con alto total
    from PyQt5.QtWidgets import QDesktopWidget

    desktop = QDesktopWidget()
    screen_geometry = desktop.availableGeometry()
    window_width = 1800
    window_height = screen_geometry.height()

    # Posicionar en coordenadas visibles
    x_position = 50
    y_position = 50
    window.setGeometry(x_position, y_position, window_width, window_height)

    # Cargar QSS stylesheet
    load_stylesheet(window)


def load_stylesheet(window):
    """Cargar QSS stylesheet - Cyber-Minimalist Theme."""
    qss_path = Path(__file__).parent.parent / "styles" / "cyber_minimalist.qss"
    try:
        if qss_path.exists():
            with open(qss_path, encoding="utf-8") as f:
                window.setStyleSheet(f.read())
    except Exception as e:
        logger.warning(f"No se pudo cargar stylesheet: {e}")


def create_compact_header(parent_layout, window):
    """
    Crear header compacto con botones de acción.

    Args:
        parent_layout: Layout donde añadir el header
        window: Instancia de ventana para conectar señales
    """
    header = QFrame()
    header.setStyleSheet("background: #1a1a2e; border-radius: 8px; padding: 8px;")
    header_layout = QHBoxLayout(header)

    # Título
    title = QLabel("🤖 URA - Centro de Comando")
    title.setStyleSheet("color: #00d4ff; font-weight: bold; font-size: 14px;")
    header_layout.addWidget(title)

    header_layout.addStretch()

    # Botones de acción
    if hasattr(window, "smart_recovery_button"):
        header_layout.addWidget(window.smart_recovery_button)
    if hasattr(window, "clean_safe_button"):
        header_layout.addWidget(window.clean_safe_button)
    if hasattr(window, "health_report_button"):
        header_layout.addWidget(window.health_report_button)

    parent_layout.addWidget(header)


def create_compact_input_bar(parent_layout, window):
    """
    Crear barra de input compacta.

    Args:
        parent_layout: Layout donde añadir la barra
        window: Instancia de ventana para conectar señales
    """

    input_layout = QHBoxLayout()

    if hasattr(window, "user_input"):
        input_layout.addWidget(window.user_input)

    if hasattr(window, "send_button"):
        input_layout.addWidget(window.send_button)

    parent_layout.addLayout(input_layout)
