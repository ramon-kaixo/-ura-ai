#!/usr/bin/env python3
"""
URA - URA Panel
Panel URA optimizado con 3 secciones verticales
"""

from PyQt5.QtWidgets import QGroupBox, QHBoxLayout, QPushButton, QTextEdit, QVBoxLayout, QWidget


def create_ura_panel_optimized(context, parent_layout):
    """
    Crear panel Ura optimizado - 3 secciones verticales

    Args:
        context: Contexto de la ventana principal (self)
        parent_layout: Layout padre donde agregar el panel
    """
    ura_group = create_ura_group(context)
    parent_layout.addWidget(ura_group)


def create_ura_group(context):
    ura_group = QGroupBox()
    ura_group.setStyleSheet("""
        QGroupBox {
            border: none;
            margin: 0px;
            padding: 0px;
        }
    """)
    ura_layout = QVBoxLayout(ura_group)
    ura_layout.setContentsMargins(0, 0, 0, 0)
    ura_layout.setSpacing(5)

    add_history_section(context, ura_layout)
    add_pending_section(context, ura_layout)
    add_decision_buttons(context, ura_layout)
    add_context_section(context, ura_layout)

    return ura_group


def add_history_section(context, parent_layout):
    context.ura_history_text = QTextEdit()
    # !important: sobreescribe el verde neón global del qss en la selección
    context.ura_history_text.setStyleSheet("""
        QTextEdit {
            background-color: #f5faff;
            color: #000000;
            border: 1px solid #cdd9e5;
            font-family: 'SF Pro Text', sans-serif;
            font-size: 15px;
            border-radius: 8px;
            selection-background-color: #cfe6ff;
            selection-color: #000000;
        }
    """)
    context.ura_history_text.setReadOnly(True)
    parent_layout.addWidget(context.ura_history_text, 6)  # 6/10 = 60%


def add_pending_section(context, parent_layout):
    context.ura_pending_text = QTextEdit()
    context.ura_pending_text.setStyleSheet("""
        QTextEdit {
            background-color: #fff9e6;
            color: #5a4a00;
            border: 2px solid #e6d37a;
            font-family: 'SF Pro Text', sans-serif;
            font-size: 15px;
            font-weight: 500;
            border-radius: 8px;
        }
    """)
    context.ura_pending_text.setReadOnly(True)
    context.ura_pending_text.setPlaceholderText(
        "Respuestas de URA pendientes de decisión aparecerán aquí..."
    )
    parent_layout.addWidget(context.ura_pending_text, 3)  # 3/10 = 30%


def add_decision_buttons(context, parent_layout):
    decision_widget = QWidget()
    decision_layout = QHBoxLayout(decision_widget)
    decision_layout.setContentsMargins(0, 5, 0, 5)
    decision_layout.setSpacing(10)

    context.send_to_windsurf_button = QPushButton("Enviar a Windsurf")
    context.send_to_windsurf_button.setToolTip(
        "Envía la respuesta pendiente de URA directamente al IDE Windsurf\n"
        "para ejecutarla como prompt en el editor activo."
    )
    context.send_to_windsurf_button.setStyleSheet("""
        QPushButton {
            background-color: #007bff;
            color: white;
            border: none;
            font-size: 13px;
            padding: 8px 16px;
            border-radius: 8px;
        }
        QPushButton:hover {
            background-color: #0056b3;
        }
    """)
    context.send_to_windsurf_button.clicked.connect(context.send_pending_to_windsurf)
    decision_layout.addWidget(context.send_to_windsurf_button)

    context.clear_pending_button = QPushButton("Borrar")
    context.clear_pending_button.setToolTip(
        "Descarta la respuesta pendiente de URA sin enviarla a Windsurf."
    )
    context.clear_pending_button.setStyleSheet("""
        QPushButton {
            background-color: #dc3545;
            color: white;
            border: none;
            font-size: 13px;
            padding: 8px 16px;
            border-radius: 8px;
        }
        QPushButton:hover {
            background-color: #c82333;
        }
    """)
    context.clear_pending_button.clicked.connect(context.clear_pending_response)
    decision_layout.addWidget(context.clear_pending_button)

    decision_layout.addStretch()
    parent_layout.addWidget(decision_widget)


def add_context_section(context, parent_layout):
    context.ura_context_text = QTextEdit()
    context.ura_context_text.setStyleSheet("""
        QTextEdit {
            background-color: #ececec;
            color: #555555;
            border: 1px solid #cccccc;
            font-family: 'SF Mono', 'Monaco', monospace;
            font-size: 12px;
            border-radius: 8px;
        }
    """)
    context.ura_context_text.setReadOnly(True)
    context.ura_context_text.setPlaceholderText("Contexto de Windsurf aparecerá aquí...")
    parent_layout.addWidget(context.ura_context_text, 1)  # 1/10 = 10%
