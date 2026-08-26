"""Tests de capacidad: verifica recursos del sistema (disco, RAM, GPU).

GX10: verifica GPU y modelos Ollama.
Anywhere: verifica espacio en disco y memoria basica.
"""

from __future__ import annotations

import shutil

import pytest

from tests.infra.conftest import REPO_ROOT, run_cmd


@pytest.mark.anywhere
class TestDiskSpace:
    """Verifica que hay suficiente espacio en disco."""

    def test_minimum_disk_space(self) -> None:
        usage = shutil.disk_usage(str(REPO_ROOT))
        free_gb = usage.free / (1024**3)
        assert free_gb > 10, f"Espacio insuficiente: {free_gb:.1f}GB libres (minimo 10GB)"


@pytest.mark.gx10
class TestGX10Capacity:
    """Verificaciones de capacidad especificas de GX10."""

    def test_ram_available(self) -> None:
        rc, out, _ = run_cmd("free -g | awk '/^Mem:/{print $7}'")
        if rc != 0:
            pytest.skip("free no disponible")
        available_gb = int(out)
        assert available_gb > 2, f"RAM insuficiente: {available_gb}GB disponible (minimo 2GB)"

    def test_nvidia_smi_works(self) -> None:
        rc, out, _ = run_cmd("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
        assert rc == 0, f"nvidia-smi no funciona: {out}"
        assert out.strip(), "nvidia-smi no retorna datos de GPU"

    def test_ollama_responds(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        assert rc == 0, "Ollama no responde en localhost:11434"
        import json

        try:
            data = json.loads(out)
            assert "models" in data, "Ollama api/tags no retorna campo 'models'"
        except (json.JSONDecodeError, KeyError) as e:
            pytest.fail(f"Ollama api/tags retorno JSON invalido: {e}")

    def test_ollama_has_models(self) -> None:
        rc, out, _ = run_cmd("curl -s http://localhost:11434/api/tags")
        if rc != 0:
            pytest.skip("Ollama no disponible")
        import json

        data = json.loads(out)
        model_count = len(data.get("models", []))
        assert model_count > 0, "Ollama no tiene modelos descargados"
