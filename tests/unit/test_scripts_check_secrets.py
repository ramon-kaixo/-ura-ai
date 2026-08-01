"""Tests for check_secrets.py."""
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent.parent / "scripts" / "pro" / "check_secrets.py"

class TestCheckSecrets:
    def test_clean(self, tmp_path):
        f = tmp_path / "a.py"
        f.write_text("x=1\n")
        r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
        assert r.returncode == 0

    def test_secret_detected(self, tmp_path):
        prefix = "sk-or-v1-"
        key = prefix + "x" * 25
        f = tmp_path / "b.py"
        f.write_text('api_key = "' + key + '"\n')
        r = subprocess.run([sys.executable, str(SCRIPT), str(f)], capture_output=True, text=True)
        assert r.returncode == 1
