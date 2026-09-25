#!/usr/bin/env python3
"""Cobertura 100x100 de core/debate/debate_engine.py."""

import pytest
import json
from unittest.mock import patch, MagicMock
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from core.debate.debate_engine import load_config, validar_esquema_salida, build_primary_prompt


class TestLoadConfig:
    """Tests para load_config()."""

    @pytest.mark.unit
    def test_load_config_exitoso(self, tmp_path):
        """Carga configuración válida."""
        config_file = tmp_path / "committee_config.json"
        test_config = {"miembro1": "rol1", "miembro2": "rol2"}
        config_file.write_text(json.dumps(test_config))
        
        with patch('core.debate.debate_engine.CONFIG_PATH', config_file):
            from core.debate.debate_engine import load_config
            config = load_config()
            assert config == test_config

    @pytest.mark.unit
    def test_load_config_archivo_no_existe(self):
        """Archivo no existe -> lanza excepción."""
        with patch('core.debate.debate_engine.CONFIG_PATH', Path("/no/existe.json")):
            from core.debate.debate_engine import load_config
            with pytest.raises(FileNotFoundError):
                load_config()


class TestValidarEsquemaSalida:
    """Tests para validar_esquema_salida()."""

    @pytest.mark.unit
    def test_sin_schema_dict_retorna_true(self):
        """Sin schema_dict -> True."""
        assert validar_esquema_salida("cualquier cosa") is True
        assert validar_esquema_salida("{}", None) is True

    @pytest.mark.unit
    def test_json_valido_con_schema_correcto(self):
        """JSON válido con schema que coincide."""
        raw = '{"nombre": "test", "valor": 123}'
        schema = {"nombre": str, "valor": int}
        assert validar_esquema_salida(raw, schema) is True

    @pytest.mark.unit
    def test_json_con_clave_faltante(self):
        """Falta clave requerida -> False."""
        raw = '{"nombre": "test"}'
        schema = {"nombre": str, "valor": int}
        assert validar_esquema_salida(raw, {"nombre": str, "valor": int}) is False

    @pytest.mark.unit
    def test_json_con_tipo_incorrecto(self):
        """Tipo incorrecto -> False."""
        raw = '{"valor": "no_es_int"}'
        assert validar_esquema_salida(raw, {"valor": int}) is False

    @pytest.mark.unit
    def test_json_invalido(self):
        """JSON malformado -> False."""
        raw = "{no es json}"
        assert validar_esquema_salida(raw, {"clave": str}) is False

    @pytest.mark.unit
    def test_json_con_marcadores_markdown_json(self):
        """JSON con marcadores ```json ... ```."""
        raw = '```json\n{"clave": "valor"}\n```'
        schema = {"clave": str}
        assert validar_esquema_salida(raw, {"clave": str}) is True

    @pytest.mark.unit
    def test_json_con_marcadores_markdown_generico(self):
        """JSON con marcadores ``` ... ```."""
        raw = '```\n{"clave": "valor"}\n```'
        schema = {"clave": str}
        assert validar_esquema_salida(raw, {"clave": str}) is True

    @pytest.mark.unit
    def test_extrae_json_entre_marcadores(self):
        """Extrae JSON entre marcadores con texto extra."""
        raw = 'Texto antes\n```json\n{"clave": "valor"}\n```\nTexto después'
        schema = {"clave": str}
        assert validar_esquema_salida(raw, {"clave": str}) is True


class TestBuildPrimaryPrompt:
    """Tests para build_primary_prompt()."""

    @pytest.mark.unit
    def test_prompt_incluye_contexto_y_plan(self):
        """Prompt incluye contexto y plan."""
        plan = "Plan de prueba"
        contexto = {"clave": "valor"}
        prompt = build_primary_prompt(plan, contexto)
        
        assert "Plan de prueba" in prompt
        assert '"clave": "valor"' in prompt
        assert "arquitecto de software" in prompt.lower()

    @pytest.mark.unit
    def test_prompt_sin_contexto(self):
        """Sin contexto -> muestra 'No disponible'."""
        prompt = build_primary_prompt("Plan test", None)
        assert "No disponible" in prompt

    @pytest.mark.unit
    def test_prompt_con_contexto_vacio(self):
        """Contexto vacío."""
        prompt = build_primary_prompt("Plan", {})
        assert "{}" in prompt or "No disponible" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
