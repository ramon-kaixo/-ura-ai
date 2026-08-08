"""Tests for core/guardian_acciones.py."""

from pathlib import Path
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


class TestInit:
    def test_crea_directorios(self, tmp_path, monkeypatch):
        monkeypatch.setattr("core.guardian_acciones.BACKUP_DIR", tmp_path / "b")
        monkeypatch.setattr("core.guardian_acciones.AUDIT_LOG", tmp_path / "a.log")
        monkeypatch.setattr("core.guardian_acciones.SANDBOX_DIR", tmp_path / "s")
        GuardianAcciones()
        assert (tmp_path / "b").is_dir()
        assert (tmp_path / "s").is_dir()

    def test_stats_iniciales_cero(self, guardian):
        assert guardian.stats["total_acciones"] == 0
        assert guardian.stats["acciones_permitidas"] == 0


class TestVerificarLicencia:
    def test_paquete_gratuito(self, guardian):
        ok, msg = guardian._verificar_licencia("numpy")
        assert ok is True
        assert "gratuito" in msg

    def test_paquete_pago(self, guardian):
        ok, msg = guardian._verificar_licencia("pycharm")
        assert ok is False
        assert "pago" in msg

    def test_pago_parcial_detectado(self, guardian):
        assert guardian._verificar_licencia("jetbrains-community")[0] is False

    def test_case_insensitive(self, guardian):
        assert guardian._verificar_licencia("IntelliJ")[0] is False


class TestDetectarPassword:
    def test_campo_password(self, guardian):
        assert guardian._detectar_password_field({"user": "a", "password": "x"}) is True

    def test_campo_pass_y_pwd(self, guardian):
        assert guardian._detectar_password_field({"pass": "x"}) is True
        assert guardian._detectar_password_field({"pwd": "x"}) is True

    def test_case_insensitive(self, guardian):
        assert guardian._detectar_password_field({"PASSWORD": "x"}) is True

    def test_sin_password(self, guardian):
        assert guardian._detectar_password_field({"user": "a", "email": "b@c.d"}) is False

    def test_no_dict(self, guardian):
        assert guardian._detectar_password_field("nope") is False

    def test_incrementa_stats(self, guardian):
        guardian._detectar_password_field({"password": "x"})
        assert guardian.stats["passwords_bloqueados"] == 1


class TestSimularSandbox:
    def test_accion_segura(self, guardian):
        assert guardian._simular_accion_sandbox("git commit -m 'fix'") is True

    def test_comando_peligroso(self, guardian):
        assert guardian._simular_accion_sandbox("rm -rf /") is False
        assert guardian._simular_accion_sandbox("mkfs.ext4 /dev/sda") is False
        assert guardian._simular_accion_sandbox("wipe disk") is False

    def test_peligroso_parcial_ok(self, guardian):
        assert guardian._simular_accion_sandbox("format string in python") is False


class TestCrearBackup:
    def test_backup_archivo(self, guardian, tmp_path):
        f = tmp_path / "cfg.py"
        f.write_text("x")
        assert guardian._crear_backup(str(f)) is True
        backups = list(guardian.backup_dir.glob("cfg.py_*.bak"))
        assert len(backups) == 1
        assert guardian.stats["backups_creados"] == 1

    def test_backup_directorio(self, guardian, tmp_path):
        d = tmp_path / "data"
        d.mkdir()
        (d / "inner.py").write_text("x")
        assert guardian._crear_backup(str(d)) is True
        assert list(guardian.backup_dir.iterdir())

    def test_ruta_no_existe(self, guardian):
        assert guardian._crear_backup("/no/existe/xyz") is False

    def test_ruta_invalida(self, guardian, tmp_path):
        assert guardian._crear_backup(str(tmp_path / "inexistente")) is False


class TestEjecutarSandbox:
    def test_3_3_exitoso(self, guardian):
        ok, msg = guardian._ejecutar_sandbox("comando seguro")
        assert ok is True
        assert "3/3" in msg
        assert guardian.stats["sandbox_exitosos"] == 1

    def test_parcial_falla(self, guardian):
        with patch.object(guardian, "_simular_accion_sandbox", return_value=False):
            ok, msg = guardian._ejecutar_sandbox("x")
        assert ok is False
        assert "0/3" in msg
        assert guardian.stats["sandbox_fallidos"] == 1

    def test_error_en_simulacion(self, guardian):
        with patch.object(guardian, "_simular_accion_sandbox", side_effect=RuntimeError("boom")):
            ok, _ = guardian._ejecutar_sandbox("x")
        assert ok is False


class TestLogAudit:
    def test_escribe_linea(self, guardian):
        guardian._log_audit("agente", "accion", "PERMITIDO", "detalle")
        contenido = guardian.audit_log.read_text()
        assert "agente" in contenido
        assert "accion" in contenido
        assert "PERMITIDO" in contenido

    def test_error_no_rompe(self, guardian, monkeypatch):
        with patch("builtins.open", side_effect=OSError("ro")):
            guardian._log_audit("a", "b", "c")  # no debe lanzar


class TestEjecutar:
    def test_instalacion_pago_bloqueada(self, guardian):
        res = guardian.ejecutar("pip install pycharm")
        assert res["success"] is False
        assert "bloqueada" in res["message"]
        assert guardian.stats["instalaciones_bloqueadas"] == 1

    def test_instalacion_gratis_denegada(self, guardian):
        with patch.object(guardian, "_autorizar_instalacion", return_value=False):
            res = guardian.ejecutar("pip install numpy")
        assert res["success"] is False
        assert "denegada" in res["message"]

    def test_instalacion_gratis_autorizada(self, guardian):
        with (
            patch.object(guardian, "_autorizar_instalacion", return_value=True),
            patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "sandbox ok")),
        ):
            res = guardian.ejecutar("pip install numpy")
        assert res["success"] is True
        assert guardian.stats["acciones_permitidas"] == 1

    def test_policia_bloquea(self, guardian):
        with (
            patch.object(guardian, "_consultar_policia", return_value=(False, "denegado")),
            patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "ok")),
        ):
            res = guardian.ejecutar("hacer algo")
        assert res["success"] is False
        assert guardian.stats["acciones_bloqueadas"] == 1

    def test_sandbox_falla_bloquea(self, guardian):
        with patch.object(guardian, "_ejecutar_sandbox", return_value=(False, "fallo")):
            res = guardian.ejecutar("hacer algo")
        assert res["success"] is False
        assert "sandbox" in res["message"]

    def test_delete_intenta_backup(self, guardian, tmp_path):
        f = tmp_path / "victima.txt"
        f.write_text("datos")
        with (
            patch.object(guardian, "_consultar_policia", return_value=(True, "ok")),
            patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "ok")),
        ):
            res = guardian.ejecutar("rm archivo", ruta=str(f))
        assert res["success"] is True
        assert guardian.stats["backups_creados"] == 1

    def test_password_field_bloquea(self, guardian):
        with (
            patch.object(guardian, "_consultar_policia", return_value=(True, "ok")),
            patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "ok")),
        ):
            res = guardian.ejecutar("guardar formulario", formulario={"password": "x"})
        assert res["success"] is False
        assert "password" in res["message"].lower()

    def test_accion_permitida(self, guardian):
        with patch.object(guardian, "_ejecutar_sandbox", return_value=(True, "sandbox ok")):
            res = guardian.ejecutar("leer archivo")
        assert res["success"] is True
        assert res["motivo_policia"] == "stub: policia desactivado"
        assert guardian.stats["total_acciones"] == 1

    def test_estado_incluye_stats(self, guardian):
        estado = guardian.estado()
        assert estado["guardian_activo"] is True
        assert "estadisticas" in estado


class TestSingleton:
    def test_get_guardian_mismo(self, monkeypatch):
        monkeypatch.setattr("core.guardian_acciones.BACKUP_DIR", Path("/tmp/x"))
        g1 = get_guardian()
        g2 = get_guardian()
        assert g1 is g2

    def test_get_guardian_no_none(self):
        assert get_guardian() is not None
