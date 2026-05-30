#!/usr/bin/env python3
"""
Panel de Configuración de Puertos - URA
Interfaz para agregar/eliminar puertos permitidos
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from PyQt5.QtWidgets import (
    QDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from core.network_audit import NetworkAuditSystem


class PortConfigPanel(QDialog):
    """Panel de configuración de puertos"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Configuración de Puertos - URA")
        self.setMinimumSize(800, 600)

        self.network_audit = NetworkAuditSystem(use_localhost=True)
        self.current_config = self.network_audit.ALLOWED_PORTS.copy()

        self.setup_ui()
        self.load_ports()

    def setup_ui(self):
        """Configurar interfaz de usuario"""
        layout = QVBoxLayout()

        # Título
        title = QLabel("Configuración de Puertos Permitidos")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        # Descripción
        desc = QLabel(
            "Gestiona los puertos permitidos en el sistema. Los puertos no autorizados se marcarán como CONFLICTO."
        )
        desc.setWordWrap(True)
        layout.addWidget(desc)

        # Tabla de puertos
        self.port_table = QTableWidget()
        self.port_table.setColumnCount(4)
        self.port_table.setHorizontalHeaderLabels(
            ["Puerto", "Servicio", "Contenido Esperado", "Acciones"]
        )
        self.port_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.port_table)

        # Formulario para agregar puerto
        add_group = QGroupBox("Agregar Nuevo Puerto")
        form_layout = QFormLayout()

        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(11434)

        self.service_input = QLineEdit()
        self.service_input.setPlaceholderText("Ej: ollama, redis, postgres")

        self.content_input = QLineEdit()
        self.content_input.setPlaceholderText("Ej: models, status (opcional)")

        form_layout.addRow("Puerto:", self.port_input)
        form_layout.addRow("Servicio:", self.service_input)
        form_layout.addRow("Contenido Esperado:", self.content_input)

        add_group.setLayout(form_layout)
        layout.addWidget(add_group)

        # Botones
        button_layout = QHBoxLayout()

        self.add_button = QPushButton("Agregar Puerto")
        self.add_button.clicked.connect(self.add_port)

        self.scan_button = QPushButton("Escanear Puertos")
        self.scan_button.clicked.connect(self.scan_ports)

        self.save_button = QPushButton("Guardar Configuración")
        self.save_button.clicked.connect(self.save_config)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.scan_button)
        button_layout.addStretch()
        button_layout.addWidget(self.save_button)

        layout.addLayout(button_layout)

        # Botón de auditoría
        audit_button = QPushButton("Ejecutar Auditoría Completa")
        audit_button.setStyleSheet("background-color: #007bff; color: white; padding: 10px;")
        audit_button.clicked.connect(self.run_full_audit)
        layout.addWidget(audit_button)

        # Botón de reserva
        reserve_group = QGroupBox("Puertos de Reserva")
        reserve_layout = QVBoxLayout()

        self.reserve_label = QLabel(str(self.network_audit.RESERVE_PORTS))
        self.reserve_label.setStyleSheet("font-family: monospace;")
        reserve_layout.addWidget(QLabel("Puertos disponibles para reasignación automática:"))
        reserve_layout.addWidget(self.reserve_label)

        reserve_group.setLayout(reserve_layout)
        layout.addWidget(reserve_group)

        self.setLayout(layout)

    def load_ports(self):
        """Cargar puertos actuales en la tabla"""
        self.port_table.setRowCount(0)

        for port, info in self.current_config.items():
            row = self.port_table.rowCount()
            self.port_table.insertRow(row)

            self.port_table.setItem(row, 0, QTableWidgetItem(str(port)))
            self.port_table.setItem(row, 1, QTableWidgetItem(info.get("service", "")))
            self.port_table.setItem(row, 2, QTableWidgetItem(info.get("expected_content", "N/A")))

            # Botón de eliminar
            delete_button = QPushButton("Eliminar")
            delete_button.clicked.connect(lambda _, p=port: self.remove_port(p))
            self.port_table.setCellWidget(row, 3, delete_button)

    def add_port(self):
        """Agregar nuevo puerto a la configuración"""
        port = self.port_input.value()
        service = self.service_input.text().strip()
        expected_content = self.content_input.text().strip()

        if not service:
            QMessageBox.warning(self, "Error", "El nombre del servicio es obligatorio")
            return

        if port in self.current_config:
            QMessageBox.warning(self, "Error", f"El puerto {port} ya está configurado")
            return

        self.current_config[port] = {
            "service": service,
            "expected_content": expected_content if expected_content else None,
        }

        self.load_ports()

        # Limpiar inputs
        self.service_input.clear()
        self.content_input.clear()

        QMessageBox.information(self, "Éxito", f"Puerto {port} agregado para {service}")

    def remove_port(self, port):
        """Eliminar puerto de la configuración"""
        reply = QMessageBox.question(
            self,
            "Confirmar",
            f"¿Estás seguro de eliminar el puerto {port}?",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            del self.current_config[port]
            self.load_ports()
            QMessageBox.information(self, "Éxito", f"Puerto {port} eliminado")

    def scan_ports(self):
        """Escanear puertos en uso"""
        self.network_audit.scan_ports()

        # Mostrar puertos no autorizados
        unauthorized = []
        for _key, port_info in self.network_audit.inventory.items():
            if not port_info.is_authorized:
                unauthorized.append(f"{port_info.port}: {port_info.process_name}")

        if unauthorized:
            msg = "Puertos no autorizados detectados:\n\n" + "\n".join(unauthorized)
            QMessageBox.warning(self, "Puertos No Autorizados", msg)
        else:
            QMessageBox.information(self, "Escaneo Completo", "Todos los puertos están autorizados")

    def run_full_audit(self):
        """Ejecutar auditoría completa"""
        try:
            report = self.network_audit.run_full_audit()

            msg = f"""Auditoría Completa:

Puertos totales: {report["total_ports"]}
Puertos Docker: {report["docker_ports"]}
Puertos nativos: {report["native_ports"]}

APIs healthy: {report["api_health"]["healthy"]}
APIs vacías: {report["api_health"]["empty"]}
APIs con error: {report["api_health"]["error"]}
"""
            QMessageBox.information(self, "Auditoría Completa", msg)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error ejecutando auditoría: {e}")

    def save_config(self):
        """Guardar configuración"""
        # Actualizar ALLOWED_PORTS en network_audit.py
        try:
            network_audit_file = Path(__file__).parent.parent / "core" / "network_audit.py"

            with open(network_audit_file) as f:
                content = f.read()

            # Generar nuevo diccionario ALLOWED_PORTS
            allowed_ports_str = "    ALLOWED_PORTS = {\n"
            for port, info in self.current_config.items():
                service = info.get("service", "")
                expected_content = info.get("expected_content")
                if expected_content:
                    allowed_ports_str += f'        {port}: {{"service": "{service}", "expected_content": "{expected_content}"}},\n'
                else:
                    allowed_ports_str += (
                        f'        {port}: {{"service": "{service}", "expected_content": None}},\n'
                    )
            allowed_ports_str += "    }"

            # Reemplazar ALLOWED_PORTS en el archivo
            import re

            pattern = r"    ALLOWED_PORTS = \{.*?\n    \}"
            content = re.sub(pattern, allowed_ports_str, content, flags=re.DOTALL)

            with open(network_audit_file, "w") as f:
                f.write(content)

            QMessageBox.information(
                self, "Éxito", "Configuración guardada en core/network_audit.py"
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Error guardando configuración: {e}")


def main():
    """Punto de entrada"""
    from PyQt5.QtWidgets import QApplication

    QApplication(sys.argv)
    panel = PortConfigPanel()
    panel.exec_()


if __name__ == "__main__":
    main()
