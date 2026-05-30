#!/usr/bin/env python3
"""
Splash Screen - Fase 5
Pantalla de bienvenida con saludo, fecha, tiempo Pamplona, barra de progreso.
"""

import logging
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from PyQt5.QtWidgets import QLabel, QVBoxLayout, QWidget, QProgressBar
    from PyQt5.QtCore import Qt

    PYQT5_AVAILABLE = True
except ImportError:
    PYQT5_AVAILABLE = False
    logger.warning("PyQt5 no disponible, usando terminal")


class SplashScreen:
    """Pantalla de bienvenida."""

    def __init__(self, use_pyqt: bool = True):
        self.use_pyqt = use_pyqt and PYQT5_AVAILABLE
        self.window = None
        self.progress_bar = None
        self.progress = 0

    def show(self):
        """Mostrar splash screen."""
        if self.use_pyqt:
            self._show_pyqt()
        else:
            self._show_terminal()

    def _show_pyqt(self):
        """Mostrar splash screen con PyQt5."""
        from PyQt5.QtWidgets import QApplication

        app = QApplication.instance()
        if app is None:
            app = QApplication(sys.argv)

        self.window = QWidget()
        self.window.setWindowTitle("URA - Iniciando")
        self.window.setFixedSize(400, 300)

        layout = QVBoxLayout()

        # Saludo
        saludo = self._get_saludo()
        label_saludo = QLabel(saludo)
        label_saludo.setAlignment(Qt.AlignCenter)
        label_saludo.setStyleSheet("font-size: 24px; font-weight: bold; color: #4facfe;")
        layout.addWidget(label_saludo)

        # Fecha
        fecha = datetime.now().strftime("%d/%m/%Y %H:%M")
        label_fecha = QLabel(fecha)
        label_fecha.setAlignment(Qt.AlignCenter)
        label_fecha.setStyleSheet("font-size: 14px; color: #a0a0b0;")
        layout.addWidget(label_fecha)

        # Tiempo Pamplona
        label_tiempo = QLabel("Pamplona: Cargando tiempo...")
        label_tiempo.setAlignment(Qt.AlignCenter)
        label_tiempo.setStyleSheet("font-size: 12px; color: #808090;")
        layout.addWidget(label_tiempo)

        # Barra de progreso
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("QProgressBar::chunk { background-color: #4facfe; }")
        layout.addWidget(self.progress_bar)

        self.window.setLayout(layout)
        self.window.show()

        # Simular carga
        self._simulate_loading()

    def _show_terminal(self):
        """Mostrar splash screen en terminal."""
        print("\n" + "=" * 50)
        print(self._get_saludo())
        print(f"Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("Pamplona: Cargando tiempo...")
        print("=" * 50)

        # Simular carga en terminal
        for i in range(0, 101, 10):
            print(f"[{'=' * (i // 10)}{' ' * (10 - i // 10)}] {i}%")
            import time

            time.sleep(0.1)

        print("URA iniciado correctamente.\n")

    def _get_saludo(self) -> str:
        """Obtener saludo según hora."""
        hora = datetime.now().hour
        if 5 <= hora < 12:
            return "¡Buenos días!"
        elif 12 <= hora < 18:
            return "¡Buenas tardes!"
        else:
            return "¡Buenas noches!"

    def _simulate_loading(self):
        """Simular carga de módulos."""
        from PyQt5.QtCore import QTimer

        def update_progress():
            self.progress += 10
            if self.progress <= 100:
                if self.progress_bar:
                    self.progress_bar.setValue(self.progress)
                QTimer.singleShot(200, update_progress)
            else:
                if self.window:
                    self.window.close()

        QTimer.singleShot(200, update_progress)

    def update_progress(self, value: int):
        """Actualizar progreso manualmente."""
        self.progress = value
        if self.progress_bar:
            self.progress_bar.setValue(value)

    def close(self):
        """Cerrar splash screen."""
        if self.window:
            self.window.close()


if __name__ == "__main__":
    splash = SplashScreen(use_pyqt=False)
    splash.show()
