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

        # Título
        title = QLabel("📋 Historial de Reparaciones")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)

        # Filtros
        filter_group = QGroupBox("Filtros")
        filter_layout = QHBoxLayout()

        filter_layout.addWidget(QLabel("Tipo de error:"))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(
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
        self.filter_combo.currentTextChanged.connect(self.filter_history)
        filter_layout.addWidget(self.filter_combo)

        filter_layout.addWidget(QLabel("Estado:"))
        self.status_combo = QComboBox()
        self.status_combo.addItems(["Todos", "Éxito", "Fallo"])
        self.status_combo.currentTextChanged.connect(self.filter_history)
        filter_layout.addWidget(self.status_combo)

        filter_layout.addStretch()

        refresh_button = QPushButton("🔄 Actualizar")
        refresh_button.clicked.connect(self.load_history)
        filter_layout.addWidget(refresh_button)

        export_button = QPushButton("📥 Exportar")
        export_button.clicked.connect(self.export_history)
        filter_layout.addWidget(export_button)

        clear_button = QPushButton("🗑️ Limpiar Historial")
        clear_button.clicked.connect(self.clear_history)
        filter_layout.addWidget(clear_button)

        filter_group.setLayout(filter_layout)
        layout.addWidget(filter_group)

        # Tabla de historial
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

        # Estadísticas
        stats_group = QGroupBox("Estadísticas")
        stats_layout = QHBoxLayout()

        self.total_label = QLabel("Total: 0")
        self.success_label = QLabel("✅ Éxito: 0")
        self.success_label.setStyleSheet("color: #00FF00;")
        self.failure_label = QLabel("❌ Fallo: 0")
        self.failure_label.setStyleSheet("color: #FF0000;")
        self.recurrent_label = QLabel("🔄 Recurrentes: 0")

        stats_layout.addWidget(self.total_label)
        stats_layout.addWidget(self.success_label)
        stats_layout.addWidget(self.failure_label)
        stats_layout.addWidget(self.recurrent_label)
        stats_layout.addStretch()

        stats_group.setLayout(stats_layout)
        layout.addWidget(stats_group)

        self.setLayout(layout)

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
        self.update_table(history)
        self.update_stats(history)

    def update_table(self, history: list[dict]):
        """Actualizar tabla con historial"""
        self.table.setRowCount(0)

        for entry in history:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Timestamp
            timestamp = entry.get("timestamp", "")
            formatted_time = self.format_timestamp(timestamp)
            self.table.setItem(row, 0, QTableWidgetItem(formatted_time))

            # Tipo de error
            error_type = entry.get("error_type", "unknown")
            self.table.setItem(row, 1, QTableWidgetItem(error_type))

            # Estado
            success = entry.get("success", False)
            status_item = QTableWidgetItem("✅ Éxito" if success else "❌ Fallo")
            if success:
                status_item.setForeground(QColor("#00FF00"))
            else:
                status_item.setForeground(QColor("#FF0000"))
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

        self.update_table(filtered)

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
                self.load_history()
                QMessageBox.information(self, "Éxito", "Historial limpiado")
            except Exception as e:
                QMessageBox.warning(self, "Error", f"Error limpiando historial: {str(e)}")

    def format_timestamp(self, timestamp: str) -> str:
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
