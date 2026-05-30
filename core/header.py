#!/usr/bin/env python3
"""
URA - Header Panel
Barra superior compacta (40px)
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QPushButton,
    QSlider,
    QWidget,
)

from ui.widgets import StatusIndicator


def create_compact_header(context, parent_layout):
    """
    Crear barra superior compacta (40px)

    Args:
        context: Contexto de la ventana principal (self)
        parent_layout: Layout padre donde agregar el header
    """
    header_widget = QWidget()
    header_widget.setFixedHeight(40)
    header_widget.setStyleSheet(
        """
        QWidget {
            background-color: #2d2d2d;
            border-bottom: 1px solid #404040;
        }
    """
    )

    header_layout = QHBoxLayout(header_widget)
    header_layout.setContentsMargins(15, 5, 15, 5)
    header_layout.setSpacing(20)

    # Izquierda: Estado de servicios
    left_widget = QWidget()
    left_layout = QHBoxLayout(left_widget)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(15)

    # Ollama
    ollama_widget = QWidget()
    ollama_layout = QHBoxLayout(ollama_widget)
    ollama_layout.setContentsMargins(0, 0, 0, 0)
    ollama_layout.setSpacing(5)

    context.ollama_indicator = StatusIndicator()
    ollama_layout.addWidget(context.ollama_indicator)

    context.ollama_status_text = QLabel("Ollama")
    context.ollama_status_text.setStyleSheet("font-size: 13px; font-weight: bold; color: #e0e0e0;")
    ollama_layout.addWidget(context.ollama_status_text)

    left_layout.addWidget(ollama_widget)

    # Windsurf
    windsurf_widget = QWidget()
    windsurf_layout = QHBoxLayout(windsurf_widget)
    windsurf_layout.setContentsMargins(0, 0, 0, 0)
    windsurf_layout.setSpacing(5)

    context.windsurf_indicator = StatusIndicator()
    windsurf_layout.addWidget(context.windsurf_indicator)

    context.windsurf_status_text = QLabel("Windsurf")
    context.windsurf_status_text.setStyleSheet(
        "font-size: 13px; font-weight: bold; color: #e0e0e0;"
    )
    windsurf_layout.addWidget(context.windsurf_status_text)

    left_layout.addWidget(windsurf_widget)

    header_layout.addWidget(left_widget)

    # Centro: Título
    title_label = QLabel("URA - Asistente Inteligente")
    title_label.setStyleSheet(
        """
        font-size: 16px;
        font-weight: bold;
        color: #e0e0e0;
    """
    )
    header_layout.addWidget(title_label)

    header_layout.addStretch()

    # Derecha: Modo interacción + verificación
    right_widget = QWidget()
    right_layout = QHBoxLayout(right_widget)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(15)

    # Toggle modo interacción
    context.mode_button_group = QButtonGroup()

    # Radio buttons compactos
    context.no_cursor_radio = QRadioButton("Sin cursor")
    context.no_cursor_radio.setStyleSheet(
        """
        QRadioButton {
            font-size: 12px;
            color: #e0e0e0;
        }
        QRadioButton::indicator {
            width: 12px;
            height: 12px;
            border-radius: 6px;
            border: 1px solid #007bff;
        }
        QRadioButton::indicator:checked {
            background-color: #007bff;
        }
    """
    )
    context.mode_button_group.addButton(context.no_cursor_radio, 0)
    context.no_cursor_radio.setChecked(True)
    context.no_cursor_radio.toggled.connect(lambda: context.change_interaction_mode("no_cursor"))
    right_layout.addWidget(context.no_cursor_radio)

    context.with_cursor_radio = QRadioButton("Con cursor")
    context.with_cursor_radio.setStyleSheet(
        """
        QRadioButton {
            font-size: 12px;
            color: #e0e0e0;
        }
        QRadioButton::indicator {
            width: 12px;
            height: 12px;
            border-radius: 6px;
            border: 1px solid #28a745;
        }
        QRadioButton::indicator:checked {
            background-color: #28a745;
        }
    """
    )
    context.mode_button_group.addButton(context.with_cursor_radio, 1)
    context.with_cursor_radio.toggled.connect(
        lambda: context.change_interaction_mode("with_cursor")
    )
    right_layout.addWidget(context.with_cursor_radio)

    # Slider velocidad (solo visible en modo cursor)
    context.speed_slider = QSlider(Qt.Horizontal)
    context.speed_slider.setRange(1, 10)
    context.speed_slider.setValue(5)
    context.speed_slider.setFixedWidth(80)
    context.speed_slider.valueChanged.connect(context.update_cursor_speed)
    context.speed_slider.hide()  # Oculto inicialmente
    right_layout.addWidget(context.speed_slider)

    # Botón verificar conexiones
    verify_button = QPushButton("Verificar")
    verify_button.setToolTip(
        "Comprueba el estado de las conexiones con Ollama y Windsurf.\n"
        "Si alguna está caída, intenta reiniciarla automáticamente."
    )
    verify_button.setStyleSheet(
        """
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            font-size: 12px;
            padding: 6px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0056b3;
        }
    """
    )
    verify_button.clicked.connect(context.check_connections)
    right_layout.addWidget(verify_button)

    # Botón certificación industrial
    cert_button = QPushButton("🏭 Certificación")
    cert_button.setToolTip("Abrir panel de certificación industrial de 4 niveles")
    cert_button.setStyleSheet(
        """
        QPushButton {
            background-color: #2ecc71;
            color: white;
            border: none;
            font-size: 12px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #27ae60;
        }
    """
    )
    cert_button.clicked.connect(context.open_certification_panel)
    right_layout.addWidget(cert_button)

    # Botón WhatsApp (Solo Lectura)
    whatsapp_button = QPushButton("📱 WhatsApp")
    whatsapp_button.setToolTip("Leer mensajes de WhatsApp (Solo Lectura)")
    whatsapp_button.setStyleSheet(
        """
        QPushButton {
            background-color: #25D366;
            color: white;
            border: none;
            font-size: 12px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #128C7E;
        }
    """
    )
    whatsapp_button.clicked.connect(context.read_whatsapp_messages)
    right_layout.addWidget(whatsapp_button)

    # Botón Correo (Gmail/Outlook)
    email_button = QPushButton("📧 Correo")
    email_button.setToolTip("Leer correos no leídos (solo lectura)")
    email_button.setStyleSheet(
        """
        QPushButton {
            background-color: #EA4335;
            color: white;
            border: none;
            font-size: 12px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #C5221F;
        }
    """
    )
    email_button.clicked.connect(context.read_email_messages)
    right_layout.addWidget(email_button)

    # Botón Telegram (Solo Lectura)
    telegram_button = QPushButton("💬 Telegram")
    telegram_button.setToolTip("Leer mensajes de Telegram (solo lectura)")
    telegram_button.setStyleSheet(
        """
        QPushButton {
            background-color: #26A5E4;
            color: white;
            border: none;
            font-size: 12px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #0088CC;
        }
    """
    )
    telegram_button.clicked.connect(context.read_telegram_messages)
    right_layout.addWidget(telegram_button)

    # Botón Instagram (Solo Lectura)
    instagram_button = QPushButton("📷 Instagram")
    instagram_button.setToolTip("Leer mensajes directos de Instagram (solo lectura)")
    instagram_button.setStyleSheet(
        """
        QPushButton {
            background-color: #E4405F;
            color: white;
            border: none;
            font-size: 12px;
            font-weight: bold;
            padding: 5px 12px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #C13584;
        }
    """
    )
    instagram_button.clicked.connect(context.read_instagram_messages)
    right_layout.addWidget(instagram_button)

    header_layout.addWidget(right_widget)

    parent_layout.addWidget(header_widget)
