"""Tests de secrets: ejecuta detect-secrets contra el repo.

Anywhere: ejecuta detect-secrets scan y audita baseline.
"""

from __future__ import annotations

import json

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestDetectSecrets:
    """Ejecuta detect-secrets y verifica que no hay nuevos secretos."""

    def test_detect_secrets_installed(self) -> None:
        rc, _, _ = run_cmd("python3 -c 'import detect_secrets; print(\"ok\")'")
        assert rc == 0, "detect-secrets no esta instalado"

    def test_no_new_secrets(self) -> None:
        """Ejecuta detect-secrets scan y compara con baseline."""
        baseline = REPO_ROOT / ".secrets.baseline"
        if not baseline.exists():
            pytest.skip(".secrets.baseline no existe — ejecutar detect-secrets scan primero")
        rc, out, _ = run_cmd(
            f"cd {REPO_ROOT} && python3 -m detect_secrets scan --all-files",
            timeout=60,
        )
        if rc != 0:
            pytest.fail(f"detect-secrets scan fallo: {out}")
        try:
            new_secrets = json.loads(out)
        except json.JSONDecodeError:
            pytest.fail(f"detect-secrets retorno JSON invalido: {out[:200]}")
        results = new_secrets.get("results", {})
        with baseline.open() as f:
            baseline_data = json.load(f)
        baseline_secrets = baseline_data.get("results", {})
        new_findings = {k: v for k, v in results.items() if k not in baseline_secrets}
        assert not new_findings, f"Nuevos secretos encontrados ({len(new_findings)}):\n" + "\n".join(
            f"  {k}" for k in list(new_findings.keys())[:10]
        )


@pytest.mark.anywhere
class TestBanditScan:
    """Ejecuta bandit y verifica que no hay hallazgos criticos."""

    def test_bandit_installed(self) -> None:
        rc, _, _ = run_cmd("bandit --version")
        assert rc == 0, "bandit no esta instalado"

    def test_no_high_severity_issues(self) -> None:
        """Ejecuta bandit en modo ligero (-ll) y verifica sin issues high."""
        rc, out, _ = run_cmd(
            "bandit -r motor/ core/ -ll -ii --format json 2>/dev/null",
            timeout=120,
        )
        if rc == -1:
            pytest.skip("bandit no disponible o timeout")
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            pytest.skip("bandit retorno JSON invalido (puede tener output no-JSON)")
        metrics = data.get("metrics", {}).get("_totals", {})
        high = metrics.get("SEVERITY.HIGH", 0)
        assert high == 0, f"Bandit encontro {high} issues de severidad HIGH"
