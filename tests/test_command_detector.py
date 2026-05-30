"""Tests for core/command_detector.py — command type detection functions."""


class TestAllDetectors:
    """Cada funcion is_*_command devuelve bool."""

    def test_screen_area_returns_bool(self):
        from core.command_detector import is_screen_area_command

        assert isinstance(is_screen_area_command("explica esta área"), bool)

    def test_windsurf_returns_bool(self):
        from core.command_detector import is_windsurf_command

        assert isinstance(is_windsurf_command("abre Windsurf"), bool)

    def test_app_returns_bool(self):
        from core.command_detector import is_app_command

        assert isinstance(is_app_command("abre safari"), bool)

    def test_manual_returns_bool(self):
        from core.command_detector import is_manual_command

        assert isinstance(is_manual_command("manual de python"), bool)

    def test_install_returns_bool(self):
        from core.command_detector import is_install_command

        assert isinstance(is_install_command("instala flask"), bool)

    def test_visual_automation_returns_bool(self):
        from core.command_detector import is_visual_automation_command

        assert isinstance(is_visual_automation_command("guíame para configurar"), bool)


class TestInstallDetection:
    """Comandos de instalacion detectados correctamente."""

    def test_instala_detected(self):
        from core.command_detector import is_install_command

        assert is_install_command("instala numpy pandas") is True

    def test_install_detected(self):
        from core.command_detector import is_install_command

        assert is_install_command("install react") is True

    def test_instalar_detected(self):
        from core.command_detector import is_install_command

        assert is_install_command("quiero instalar django") is True


class TestScreenAreaDetection:
    """Comandos de vision/area detectados correctamente."""

    def test_analiza_esta_parte(self):
        from core.command_detector import is_screen_area_command

        assert is_screen_area_command("analiza esta parte de la pantalla") is True

    def test_explica_esta_area(self):
        from core.command_detector import is_screen_area_command

        assert is_screen_area_command("explica esta área") is True

    def test_que_es_esto(self):
        from core.command_detector import is_screen_area_command

        assert is_screen_area_command("qué es esto de aquí") is True


class TestNormalMessages:
    """Mensajes normales no son detectados por ningun detector."""

    def test_normal_chat_not_detected(self):
        from core.command_detector import (
            is_screen_area_command,
            is_windsurf_command,
            is_app_command,
            is_manual_command,
            is_install_command,
            is_visual_automation_command,
        )

        mensaje = "hola ura cómo estás hoy"
        assert is_screen_area_command(mensaje) is False
        assert is_windsurf_command(mensaje) is False
        assert is_app_command(mensaje) is False
        assert is_manual_command(mensaje) is False
        assert is_install_command(mensaje) is False
        assert is_visual_automation_command(mensaje) is False
