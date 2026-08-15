"""Tests de cobertura para core/guardian_acciones.py (TASK-20260815-003, P2).

Cubren las ramas restantes: casos de error, rutas no archivo/directorio,
autorización de instalación con/sin precio, parsing de acciones y
la rama de aviso de backup fallido en ejecutar().
"""

import os
from unittest.mock import patch

import pytest

from core.guardian_acciones import GuardianAcciones, get_guardian


@pytest.fixture
def guardian(tmp_path, monkeypatch):
    monkeypatch.setattr("core.guardian_acciones.BACKUP_DIR", tmp_path / "backups")
    monkeypatch.setattr("core.guardian_acciones.AUDIT_LOG", tmp_path / "audit.log")
    monkeypatch.setattr("core.guardian_acciones.SANDBOX_DIR", tmp_path / "sandbox")
    g = GuardianAcciones()
    return g


class TestCrearBackupExtras:
    def test_ruta_ni_archivo_ni_directorio(self, guardian, tmp_path):
        fifo = tmp_path / "pipe"
        os.mkfifo(fifo)
        assert fifo.exists()
        assert not fifo.is_file()
        assert not fifo.is_dir()
        assert guardian._crear_backup(str(fifo)) is False

    def test_error_en_backup(self, guardian, tmp_path):
        f = tmp_path / "cfg.py"
        f.write_text("x")
        with patch("core.guardian_acciones.shutil.copy2", side_effect=OSError("io")):
            assert guardian._crear_backup(str(f)) is False


class TestEjecutarSandboxExtras:
    def test_error_fuera_del_bucle(self, guardian):
        class _StatQueFalla:
            def __iadd__(self, otro):
                raise RuntimeError("boom")

        guardian.stats["sandbox_exitosos"] = _StatQueFalla()
        ok, msg = guardian._ejecutar_sandbox("comando seguro")
        assert ok is False
        assert "boom" in msg


class TestVerificarLicenciaExtras:
    def test_error_no_str(self, guardian):
        ok, msg = guardian._verificar_licencia(123)
        assert ok is False
        assert "Error" in msg


class TestAutorizarInstalacion:
    def test_autoriza_sin_precio(self, guardian):
        with patch("builtins.input", return_value="s"):
            assert guardian._autorizar_instalacion("paquete") is True

    def test_deniega_sin_precio(self, guardian):
        with patch("builtins.input", return_value="n"):
            assert guardian._autorizar_instalacion("paquete") is False

    def test_autoriza_con_precio(self, guardian):
        with patch("builtins.input", return_value="sí"):
            assert guardian._autorizar_instalacion("paquete", precio=10.5) is True

    def test_autoriza_con_si(self, guardian):
        with patch("builtins.input", return_value="  SI  "):
            assert guardian._autorizar_instalacion("paquete", precio=1) is True

    def test_error_input(self, guardian):
        with patch("builtins.input", side_effect=EOFError("eof")):
            assert guardian._autorizar_instalacion("paquete") is False


class TestReglaInstalacionExtras:
    def test_no_es_instalacion(self, guardian):
        assert guardian._regla_instalacion("leer archivo") is None

    def test_instalacion_sin_paquete(self, guardian):
        assert guardian._regla_instalacion("pip install") is None

    def test_bloqueada_audita(self, guardian):
        res = guardian._regla_instalacion("brew install pycharm")
        assert res is not None
        assert res["success"] is False
        assert "bloqueada" in res["message"]
        assert guardian.audit_log.exists()
        assert "BLOQUEADO" in guardian.audit_log.read_text()


class TestReglaCopiaPrevia:
    def test_no_borrado(self, guardian):
        assert guardian._regla_copia_previa("leer archivo") is None

    def test_borrado_sin_ruta_kwarg(self, guardian):
        assert guardian._regla_copia_previa("rm archivo.txt") == "Backup falló, pero se procede con la acción"

    def test_borrado_ruta_vacia_parsea(self, guardian):
        assert guardian._regla_copia_previa("unlink objetivo", ruta="") == "Backup falló, pero se procede con la acción"

    def test_borrado_palabra_unica(self, guardian):
        assert guardian._regla_copia_previa("delete") is None

    def test_borrado_backup_ok(self, guardian, tmp_path):
        f = tmp_path / "victima.txt"
        f.write_text("datos")
        assert guardian._regla_copia_previa("delete victim", ruta=str(f)) is None
        assert guardian.stats["backups_creados"] == 1


class TestEjecutarExtras:
    def test_aviso_backup_fallido(self, guardian):
        with patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "sandbox ok")):
            res = guardian.ejecutar("rm archivo.txt")
        assert res["success"] is True
        assert res["sandbox"] == "sandbox ok"
        assert guardian.stats["backups_creados"] == 0

    def test_formulario_no_dict_pasa(self, guardian):
        with patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "ok")):
            res = guardian.ejecutar("guardar", formulario="no-dict")
        assert res["success"] is True


class TestMostrarReglas:
    def test_mostrar_reglas(self, guardian):
        guardian.mostrar_reglas()


class TestSingletonExtras:
    def test_reset_singleton(self, monkeypatch):
        monkeypatch.setattr("core.guardian_acciones._guardian_instance", None)
        g1 = get_guardian()
        assert g1 is not None
