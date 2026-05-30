#!/usr/bin/env python3
"""
URA - Input Bar Panel
Barra inferior compacta con botones Pro
"""

from PyQt5.QtWidgets import QHBoxLayout, QLineEdit, QPushButton, QWidget

from core.ura_config import config
from ui.widgets import CompactVoiceButton


def create_compact_input_bar(context, parent_layout):
    """
    Crear barra inferior compacta con botones Pro

    Args:
        context: Contexto de la ventana principal (self)
        parent_layout: Layout padre donde agregar la barra
    """
    input_bar = QWidget()
    input_bar.setMaximumHeight(60)

    input_layout = QHBoxLayout(input_bar)
    input_layout.setContentsMargins(15, 10, 15, 10)
    input_layout.setSpacing(10)

    # Botones Pro (izquierda)
    pro_widget = QWidget()
    pro_layout = QHBoxLayout(pro_widget)
    pro_layout.setContentsMargins(0, 0, 0, 0)
    pro_layout.setSpacing(8)

    # Botón Salud
    context.health_button = QPushButton("⚡ Salud")
    context.health_button.setObjectName("health_button")
    context.health_button.setToolTip(
        "Genera un informe de salud del sistema:\nCPU, RAM, Ollama, Windsurf y servicios activos."
    )
    context.health_button.clicked.connect(context.handle_health_report_command)
    pro_layout.addWidget(context.health_button)

    # Botón Limpiar
    context.clean_button = QPushButton("🗑️ Limpiar")
    context.clean_button.setObjectName("clean_button")
    context.clean_button.setToolTip(
        "Borra el contenido visible de todos los paneles\n"
        "(historial, pendientes y contexto). No afecta a los archivos."
    )
    context.clean_button.clicked.connect(context.clear_context)
    pro_layout.addWidget(context.clean_button)

    # Botón Recuperación Inteligente (antes: Smart Recovery)
    context.smart_recovery_button = QPushButton("🛟 Recuperación Inteligente")
    context.smart_recovery_button.setObjectName("smart_recovery_button")
    context.smart_recovery_button.setToolTip(
        "Pulsa para restaurar el sistema y limpiar errores sin perder tus datos de hoy.\n\n"
        "• Restaura el núcleo desde el backup de las ~03:00 AM\n"
        "• Preserva facturas, logs y outputs generados hoy\n"
        "• Reinstala librerías Python faltantes automáticamente\n"
        "• Requiere validación Telegram + Face ID/Touch ID"
    )
    context.smart_recovery_button.setStyleSheet(
        "QPushButton#smart_recovery_button { background-color: #6f42c1; color: #fff;"
        " border: none; padding: 6px 12px; border-radius: 6px; font-weight: 600; }"
        "QPushButton#smart_recovery_button:hover { background-color: #5a32a3; }"
        "QPushButton#smart_recovery_button:disabled { background-color: #444; color: #888; }"
    )
    context.smart_recovery_button.clicked.connect(context.handle_smart_recovery)
    if not config.smart_recovery_available:
        context.smart_recovery_button.setEnabled(False)
        context.smart_recovery_button.setToolTip("Módulo smart_recovery no disponible")
    pro_layout.addWidget(context.smart_recovery_button)

    # Botón Limpieza Segura (genera lista + Face ID antes de borrar)
    context.clean_safe_button = QPushButton("🧹 Limpieza Segura")
    context.clean_safe_button.setObjectName("clean_safe_button")
    context.clean_safe_button.setToolTip(
        "Genera lista_limpieza.txt con los 'restos de obra'.\n\n"
        "• No borra nada sin tu permiso\n"
        "• Muestra la lista en el panel derecho\n"
        "• Requiere validación Face ID/Touch ID antes de eliminar"
    )
    context.clean_safe_button.setStyleSheet(
        "QPushButton#clean_safe_button { background-color: #0ea5e9; color: #fff;"
        " border: none; padding: 6px 12px; border-radius: 6px; font-weight: 600; }"
        "QPushButton#clean_safe_button:hover { background-color: #0284c7; }"
    )
    context.clean_safe_button.clicked.connect(context.handle_clean_safe)
    pro_layout.addWidget(context.clean_safe_button)

    # Botón Turbo/Pro
    context.turbo_button = QPushButton("🚀 Turbo")
    context.turbo_button.setObjectName("turbo_button")
    context.turbo_button.setToolTip(
        "Activa/desactiva el modo Turbo: usa un modelo Ollama más rápido\n"
        "a cambio de respuestas menos matizadas. Útil para dictado o consultas breves."
    )
    context.turbo_button.setCheckable(True)
    context.turbo_button.clicked.connect(context.toggle_turbo_mode)
    pro_layout.addWidget(context.turbo_button)

    input_layout.addWidget(pro_widget)

    # Campo de texto de una línea
    context.user_input = QLineEdit()
    context.user_input.setPlaceholderText("Escribe tu mensaje aquí para Ura...")
    context.user_input.setStyleSheet("""
        QLineEdit {
            background-color: #ffffff;
            color: #000000;
            border: 1px solid #cdd9e5;
            border-radius: 6px;
            padding: 6px 8px;
            selection-background-color: #cfe6ff;
            selection-color: #000000;
        }
        QLineEdit:focus { border: 1px solid #3b82f6; }
    """)
    context.user_input.returnPressed.connect(context.send_message)
    input_layout.addWidget(context.user_input, 1)

    # Botones de voz compactos
    voice_widget = QWidget()
    voice_layout = QHBoxLayout(voice_widget)
    voice_layout.setContentsMargins(0, 0, 0, 0)
    voice_layout.setSpacing(5)

    # Micrófono
    context.mic_button = CompactVoiceButton("mic", "Dictado por voz", "#007bff")
    context.mic_button.clicked.connect(context.start_voice_input)
    voice_layout.addWidget(context.mic_button)

    # Altavoz
    context.speaker_button = CompactVoiceButton("speaker", "Leer respuesta en voz alta", "#28a745")
    context.speaker_button.clicked.connect(context.speak_response)
    voice_layout.addWidget(context.speaker_button)

    # Conversación continua
    context.conversation_button = CompactVoiceButton(
        "chat", "Conversación continua por voz", "#17a2b8"
    )
    context.conversation_button.clicked.connect(context.toggle_continuous_conversation)
    voice_layout.addWidget(context.conversation_button)

    input_layout.addWidget(voice_widget)

    # Botón ENVIAR
    context.send_button = QPushButton("ENVIAR")
    context.send_button.setToolTip("Envía el mensaje escrito a URA (equivalente a pulsar Intro).")
    context.send_button.setEnabled(True)
    context.send_button.clicked.connect(context.send_message)
    input_layout.addWidget(context.send_button)

    parent_layout.addWidget(input_bar)
