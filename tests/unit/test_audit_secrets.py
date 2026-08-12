"""Tests de audit_secrets.py — precisión de la heurística refinada.

Cubre el refinamiento de 2026-08-13 (hallazgo hallazgos-fondo.md):
señal fuerte por prefijo, señal genérica solo en asignación sensible,
exclusión de regex y autorreferencia, URLs con credenciales reales.
"""

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts" / "pro"))

import audit_secrets as a

URA = Path(__file__).parent.parent.parent


def _tipos(texto: str, nombre: str = "x.py") -> list[str]:
    return [f.type for f in a._check_hardcoded_strings(Path(nombre), texto)]


class TestStrongKeys:
    def test_sk_prefijo_detectado(self):
        assert "hardcoded_secret" in _tipos('API_KEY = "sk-abcdefghijklmnopqrstuvwx123456"')

    def test_gsk_prefijo_detectado(self):
        assert "hardcoded_secret" in _tipos('clave = "gsk_abcdefghijklmnopqrstuvwx123456"')

    def test_akia_detectado(self):
        assert "hardcoded_secret" in _tipos('AWS_KEY = "AKIAIOSFODNN7EXAMPLE123456"')

    def test_fuerte_no_duplica_con_generica(self):
        tipos = _tipos('API_KEY = "sk-abcdefghijklmnopqrstuvwx123456"')
        assert tipos.count("hardcoded_secret") == 1


class TestGenericKeys:
    def test_generica_con_var_sensible_detectada(self):
        assert "hardcoded_secret" in _tipos('PASSWORD = "ura_1972_secure_autonomous"')

    def test_generica_sin_var_sensible_no(self):
        assert _tipos('x = "abcdefghijklmnopqrstuvwxyz0123456789"') == []

    def test_generica_sin_asignacion_no(self):
        assert _tipos('print("abcdefghijklmnopqrstuvwxyz0123456789")') == []

    def test_jwt_fuera_de_alcance(self):
        assert _tipos('token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMj"') == []

    def test_longitud_corta_no(self):
        assert _tipos('password = "abc123"') == []


class TestFiltros:
    def test_regex_no_detectado(self):
        assert _tipos('PATTERN = re.compile(r"sk-[A-Za-z0-9]{10,}|gsk_")') == []

    def test_comentario_no_detectado(self):
        assert _tipos("# PASSWORD = 'sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'") == []

    def test_autorreferencia_excluida(self):
        for nombre in ("audit_secrets.py", "audit_git_secrets.py"):
            assert a._check_hardcoded_strings(Path(nombre), 'PASSWORD = "sk-aaaaaaaaaaaaaaaaaaaaaaaa"') == []


class TestCredentialUrl:
    def test_credenciales_reales_detectadas(self):
        assert "credential_url" in _tipos('url = "http://admin:secret123@host"')

    def test_credenciales_cortas_no(self):
        assert _tipos('url = "http://user:pa@host"') == []

    def test_regex_url_excluido(self):
        assert _tipos('r = re.compile(r"://[^:]+:[^@]+@")') == []


class TestContrato:
    def test_json_estructura(self, tmp_path):
        py = tmp_path / "con_secreto.py"
        py.write_text('TOKEN = "sk-abcdefghijklmnopqrstuvwx123456"\n', encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(URA / "scripts" / "pro" / "audit_secrets.py"), "--json", f"--path={py}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        d = json.loads(proc.stdout)
        assert d["total"] == 2
        assert d["by_severity"]["critical"] == 1
        assert d["by_severity"]["high"] == 1
        assert d["findings"][0]["type"] == "hardcoded_secret"

    def test_sin_hallazgos_exit_0(self, tmp_path):
        py = tmp_path / "limpio.py"
        py.write_text("x = 1\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(URA / "scripts" / "pro" / "audit_secrets.py"), f"--path={py}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert "OK" in proc.stdout

    def test_json_sin_hallazgos_exit_0(self, tmp_path):
        py = tmp_path / "limpio2.py"
        py.write_text("x = 1\n", encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(URA / "scripts" / "pro" / "audit_secrets.py"), "--json", f"--path={py}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
        assert json.loads(proc.stdout)["total"] == 0

    def test_fail_critical_con_critico_exit_1(self, tmp_path):
        py = tmp_path / "crit.py"
        py.write_text('TOKEN = "sk-abcdefghijklmnopqrstuvwx123456"\n', encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(URA / "scripts" / "pro" / "audit_secrets.py"), "--fail-critical", f"--path={py}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        assert "CRITICAL" in proc.stdout

    def test_fail_critical_solo_high_exit_0(self, tmp_path):
        py = tmp_path / "high_only.py"
        py.write_text('import os\nos.environ.get("GROQ_API_KEY", "")\n', encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(URA / "scripts" / "pro" / "audit_secrets.py"), "--fail-critical", f"--path={py}"],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 0
