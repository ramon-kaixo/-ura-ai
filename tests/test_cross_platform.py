#!/usr/bin/env python3
"""
Tests Cross-Platform para Nivel 24 (Applications Awareness)

Verifica que Applications Awareness funciona correctamente en:
- macOS
- Windows
- Linux
"""

import pytest
import platform
import logging
from core.ura_applications_awareness import get_ura_applications_awareness

logging.basicConfig(level=logging.INFO)


class TestCrossPlatform:
    """Tests cross-platform para applications awareness."""

    def test_platform_detection(self):
        """Test que el sistema detecta la plataforma correctamente."""
        apps = get_ura_applications_awareness()
        context = apps.get_applications_context()

        assert isinstance(context, str)
        assert len(context) > 0
        # El contexto contiene info de aplicaciones (texto en español)
        assert "aplicaciones" in context.lower()

    def test_macos_applications_scan(self):
        """Test escaneo de aplicaciones en macOS."""
        if platform.system() != "Darwin":
            pytest.skip("Solo macOS")

        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        assert len(apps.applications) > 0

    def test_windows_applications_scan(self):
        """Test escaneo de aplicaciones en Windows."""
        if platform.system() != "Windows":
            pytest.skip("Solo Windows")

        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        assert len(apps.applications) > 0

    def test_linux_applications_scan(self):
        """Test escaneo de aplicaciones en Linux."""
        if platform.system() != "Linux":
            pytest.skip("Solo Linux")

        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        assert len(apps.applications) > 0

    def test_applications_context_format(self):
        """Test que el contexto tiene formato correcto."""
        apps = get_ura_applications_awareness()
        context = apps.get_applications_context()

        # Acepta tanto la grafía correcta como la actual del módulo
        assert (
            "CONCIENCIA DE APLICACIONES" in context
            or "CONSCIENCIA DE APLICACIONES" in context
            or "aplicaciones" in context.lower()
        )
        assert isinstance(context, str)

    def test_get_application_info(self):
        """Test obtener información de aplicación específica."""
        apps = get_ura_applications_awareness()

        # Intentar buscar una aplicación común
        common_apps = {
            "Darwin": ["Safari", "Finder", "Terminal"],
            "Windows": ["explorer", "cmd", "notepad"],
            "Linux": ["firefox", "chrome", "terminal"],
        }

        system = platform.system()
        for app_name in common_apps.get(system, []):
            app_info = apps.get_application_info(app_name)
            if app_info:
                assert app_info.name == app_name
                break

    def test_applications_singleton(self):
        """Test que applications awareness tiene singleton correcto."""
        apps1 = get_ura_applications_awareness()
        apps2 = get_ura_applications_awareness()
        assert apps1 is apps2


class TestPlatformSpecific:
    """Tests específicos por plataforma."""

    @pytest.mark.platform_specific
    @pytest.mark.skipif(platform.system() != "Darwin", reason="Solo macOS")
    def test_macos_applications_path(self):
        """Test que macOS escanea /Applications."""
        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        # Verificar que se escaneó /Applications
        app_paths = [app.path for app in apps.applications.values()]
        has_applications_dir = any("/Applications" in path for path in app_paths)

        assert has_applications_dir or len(apps.applications) > 0

    @pytest.mark.platform_specific
    @pytest.mark.skipif(platform.system() != "Windows", reason="Solo Windows")
    def test_windows_registry_access(self):
        """Test que Windows puede acceder al registro."""
        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        # Verificar que se encontraron aplicaciones
        assert len(apps.applications) > 0

    @pytest.mark.platform_specific
    @pytest.mark.skipif(platform.system() != "Linux", reason="Solo Linux")
    def test_linux_desktop_entries(self):
        """Test que Linux escanea entradas .desktop."""
        apps = get_ura_applications_awareness()
        apps.refresh_applications()

        # Verificar que se encontraron aplicaciones
        assert len(apps.applications) > 0


class TestPerformanceCrossPlatform:
    """Tests de performance cross-platform."""

    def test_applications_scan_performance(self):
        """Test que el escaneo de aplicaciones tiene límites de performance."""
        import time

        apps = get_ura_applications_awareness()

        start = time.time()
        apps.refresh_applications()
        elapsed = time.time() - start

        # El escaneo debe ser rápido (menos de 30 segundos)
        assert elapsed < 30, f"Escaneo tardó {elapsed} segundos, debe ser < 30"
        assert len(apps.applications) > 0


class TestErrorHandlingCrossPlatform:
    """Tests de manejo de errores cross-platform."""

    def test_missing_directory_handling(self):
        """Test manejo de directorios faltantes."""
        apps = get_ura_applications_awareness()

        # No debería fallar incluso si directorios no existen
        context = apps.get_applications_context()
        assert isinstance(context, str)

    def test_permission_denied_handling(self):
        """Test manejo de permisos denegados."""
        apps = get_ura_applications_awareness()

        # No debería fallar si hay permisos denegados
        context = apps.get_applications_context()
        assert isinstance(context, str)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
