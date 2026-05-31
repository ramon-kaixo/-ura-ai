#!/usr/bin/env python3
"""
core/repair_history_panel.py - Panel de Visualización de Historial de Reparaciones
Muestra el historial de reparaciones del sistema de auto-reparación
"""

import json
from datetime import datetime
from pathlib import Path

from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor, QFont
from PyQt5.QtWidgets import (
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class RepairHistoryPanel(QWidget):
    """Panel de visualización de historial de reparaciones"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.repair_history_file = Path(__file__).parent.parent / "data" / "repair_history.json"
        self.init_ui()
        self.load_history()


def init_ui(self):
    """Inicializar interfaz de usuario"""
    layout = QVBoxLayout()
    add_title(layout)
    add_filter_group(layout)
    add_table(layout)
    add_stats_group(layout)


def add_title(layout):
    title = QLabel("📋 Historial de Reparaciones")
    title.setFont(QFont("Arial", 16, QFont.Bold))
    title.setAlignment(Qt.AlignCenter)
    layout.addWidget(title)


def add_filter_group(layout):
    filter_group = QGroupBox("Filtros")
    filter_layout = QHBoxLayout()
    add_filter_combo(filter_layout, "Tipo de error:", self.filter_combo)
    add_filter_combo(filter_layout, "Estado:", self.status_combo)
    add_buttons(filter_layout)
    filter_group.setLayout(filter_layout)
    layout.addWidget(filter_group)


def add_filter_combo(layout, label_text, combo_box):
    layout.addWidget(QLabel(label_text))
    combo_box.addItems(
        [
            "Todos",
            "missing_module",
            "ollama",
            "redis",
            "missing_file",
            "import_error",
            "permission",
            "key_error",
            "attribute_error",
            "type_error",
            "unknown",
        ]
    )
    combo_box.currentTextChanged.connect(self.filter_history)


def add_buttons(layout):
    refresh_button = QPushButton("🔄 Actualizar")
    refresh_button.clicked.connect(self.load_history)
    layout.addWidget(refresh_button)

    export_button = QPushButton("📥 Exportar")
    export_button.clicked.connect(self.export_history)
    layout.addWidget(export_button)

    clear_button = QPushButton("🗑️ Limpiar Historial")
    clear_button.clicked.connect(self.clear_history)
    layout.addWidget(clear_button)


def add_table(layout):
    self.table = QTableWidget()
    self.table.setColumnCount(5)
    self.table.setHorizontalHeaderLabels(["Timestamp", "Tipo", "Estado", "Mensaje"])
    self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
    self.table.setAlternatingRowColors(True)
    self.table.setStyleSheet(
        """
        QTableWidget {
            background-color: #1E1E1E;
            color: #E0E0E0;
            alternate-background-color: #2D2D2D;
            gridline-color: #404040;
        }
        QTableWidget::item {
            padding: 5px;
        }
        QHeaderView::section {
            background-color: #3A3A3A;
            color: #E0E0E0;
            padding: 5px;
            border: 1px solid #404040;
            font-weight: bold;
        }
    """
    )
    layout.addWidget(self.table)


def add_stats_group(layout):
    stats_group = create_stats_group()
    layout.addWidget(stats_group)


def create_stats_group():
    stats_layout = QHBoxLayout()
    stats_layout.addWidget(create_total_label())
    stats_layout.addWidget(create_success_label())
    stats_layout.addWidget(create_failure_label())
    stats_layout.addWidget(create_recurrent_label())
    stats_layout.addStretch()
    stats_group = QGroupBox("Estadísticas")
    stats_group.setLayout(stats_layout)
    return stats_group


def create_total_label():
    label = QLabel("Total: 0", self.total_label)
    return label


def create_success_label():
    label = QLabel("✅ Éxito: 0", self.success_label)
    return label


def create_failure_label():
    label = QLabel("❌ Fallo: 0", self.failure_label)
    return label


def create_recurrent_label():
    label = QLabel("🔄 Recurrentes: 0", self.recurrent_label)
    return label


def load_history(self):
    """Cargar historial de reparaciones"""
    history = []

    if self.repair_history_file.exists():
        try:
            with open(self.repair_history_file) as f:
                history = json.load(f)
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error cargando historial: {str(e)}")

    self.current_history = history
    update_table(history)
    update_stats(history)


def filter_history(self):
    """Filtrar historial según selección"""
    if not hasattr(self, "current_history"):
        return

    error_type_filter = self.filter_combo.currentText()
    status_filter = self.status_combo.currentText()

    filtered = []

    for entry in self.current_history:
        # Filtrar por tipo de error
        if error_type_filter != "Todos":
            if entry.get("error_type", "") != error_type_filter:
                continue

        # Filtrar por estado
        if status_filter != "Todos":
            success = entry.get("success", False)
            if status_filter == "Éxito" and not success:
                continue
            if status_filter == "Fallo" and success:
                continue

        filtered.append(entry)

    update_table(filtered)


def export_history(self):
    """Exportar historial a JSON"""
    if not hasattr(self, "current_history") or not self.current_history:
        QMessageBox.information(self, "Info", "No hay historial para exportar")
        return

    from PyQt5.QtWidgets import QFileDialog

    file_path, _ = QFileDialog.getSaveFileName(
        self,
        "Exportar Historial",
        str(Path.home() / "Desktop"),
        "JSON Files (*.json);;CSV Files (*.csv)",
    )

    if file_path:
        try:
            if file_path.endswith(".json"):
                with open(file_path, "w") as f:
                    json.dump(self.current_history, f, indent=2)
            elif file_path.endswith(".csv"):
                import csv

                with open(file_path, "w", newline="") as f:
                    writer = csv.DictWriter(
                        f, fieldnames=["timestamp", "error_type", "success", "repair_message"]
                    )
                    writer.writeheader()
                    writer.writerows(self.current_history)

            QMessageBox.information(self, "Éxito", f"Historial exportado a {file_path}")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error exportando historial: {str(e)}")


def clear_history(self):
    """Limpiar historial"""
    reply = QMessageBox.question(
        self,
        "Confirmar",
        "¿Estás seguro de que quieres limpiar el historial de reparaciones?",
        QMessageBox.Yes | QMessageBox.No,
    )

    if reply == QMessageBox.Yes:
        try:
            with open(self.repair_history_file, "w") as f:
                json.dump([], f)
            load_history()
            QMessageBox.information(self, "Éxito", "Historial limpiado")
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Error limpiando historial: {str(e)}")


def update_table(self, history: list[dict]):
    """Actualizar tabla con historial"""
    self.table.setRowCount(0)

    for entry in history:
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Timestamp
        timestamp = entry.get("timestamp", "")
        formatted_time = format_timestamp(timestamp)
        self.table.setItem(row, 0, QTableWidgetItem(formatted_time))

        # Tipo de error
        error_type = entry.get("error_type", "unknown")
        self.table.setItem(row, 1, QTableWidgetItem(error_type))

        # Estado
        success = entry.get("success", False)
        status_item = create_status_label(success)
        self.table.setItem(row, 2, status_item)

        # Mensaje
        repair_message = entry.get("repair_message", "")
        self.table.setItem(row, 3, QTableWidgetItem(repair_message))

    self.table.resizeColumnsToContents()


def update_stats(self, history: list[dict]):
    """Actualizar estadísticas"""
    total = len(history)
    success = sum(1 for entry in history if entry.get("success", False))
    failure = total - success

    # Calcular recurrentes
    error_counts = {}
    for entry in history:
        if not entry.get("success", False):
            error_type = entry.get("error_type", "unknown")
            error_counts[error_type] = error_counts.get(error_type, 0) + 1

    recurrent = sum(1 for count in error_counts.values() if count >= 3)

    self.total_label.setText(f"Total: {total}")
    self.success_label.setText(f"✅ Éxito: {success}")
    self.failure_label.setText(f"❌ Fallo: {failure}")
    self.recurrent_label.setText(f"🔄 Recurrentes: {recurrent}")


def create_status_label(success: bool):
    """Crear etiqueta de estado"""
    status_item = QTableWidgetItem("✅ Éxito" if success else "❌ Fallo")
    if success:
        status_item.setForeground(QColor("#00FF00"))
    else:
        status_item.setForeground(QColor("#FF0000"))
    return status_item


def format_timestamp(timestamp: str) -> str:
    """Formatear timestamp"""
    try:
        dt = datetime.fromisoformat(timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return timestamp


if __name__ == "__main__":
    import sys

    from PyQt5.QtWidgets import QApplication

    app = QApplication(sys.argv)

    panel = RepairHistoryPanel()
    panel.setWindowTitle("Panel de Historial de Reparaciones")
    panel.resize(900, 600)
    panel.show()

    sys.exit(app.exec_())
