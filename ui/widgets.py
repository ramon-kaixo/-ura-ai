#!/usr/bin/env python3
"""
URA - UI Widgets
Widgets personalizados para la interfaz de URA
"""

from PyQt5.QtCore import Qt, QTimer
from PyQt5.QtGui import QColor, QPainter
from PyQt5.QtWidgets import QPushButton, QWidget


class StatusIndicator(QWidget):
    """Widget personalizado para indicadores de estado compactos"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(16, 16)
        self.status = False
        self.animation_timer = QTimer()
        self.animation_timer.timeout.connect(self.animate_pulse)
        self.animation_value = 0

    def set_status(self, connected):
        self.status = connected
        if connected:
            self.animation_timer.start(150)
        else:
            self.animation_timer.stop()
        self.update()

    def animate_pulse(self):
        self.animation_value = (self.animation_value + 20) % 360
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        if self.status:
            hue = 120 + (self.animation_value % 60) - 30
            color = QColor.fromHsv(hue, 200, 200)
        else:
            color = QColor(220, 53, 69)

        painter.setBrush(color)
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(2, 2, 12, 12)


class CompactVoiceButton(QPushButton):
    """Botón de voz compacto con solo icono"""

    def __init__(self, icon_text, tooltip_text, color="#007bff", parent=None):
        super().__init__(icon_text, parent)
        self.setFixedSize(32, 32)
        self.setToolTip(tooltip_text)
        self.base_color = color
        self.setStyleSheet(f"""
            QPushButton {{
                background-color: {color};
                color: white;
                border: none;
                border-radius: 16px;
                font-size: 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {self._darken_color(color)};
            }}
            QPushButton:pressed {{
                background-color: {self._darken_color(color, 0.8)};
            }}
        """)

    def _darken_color(self, color, factor=0.9):
        """Oscurecer color"""
        if color.startswith("#"):
            r = int(color[1:3], 16)
            g = int(color[3:5], 16)
            b = int(color[5:7], 16)
            r = int(r * factor)
            g = int(g * factor)
            b = int(b * factor)
            return f"#{r:02x}{g:02x}{b:02x}"
        return color
