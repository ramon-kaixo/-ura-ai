"""Tests for core/code_agents/generators/registry.py — code generators registry."""


class TestListar:
    """listar() — returns available generators."""

    def test_returns_list(self):
        from core.code_agents.generators.registry import listar

        result = listar()
        assert isinstance(result, list)

    def test_returns_10_generators(self):
        from core.code_agents.generators.registry import listar

        result = listar()
        assert len(result) == 10

    def test_each_generator_has_tipo(self):
        from core.code_agents.generators.registry import listar

        for item in listar():
            assert "tipo" in item, f"Missing 'tipo' in {item}"

    def test_each_generator_has_descripcion(self):
        from core.code_agents.generators.registry import listar

        for item in listar():
            assert "descripcion" in item, f"Missing 'descripcion' in {item}"

    def test_known_types_present(self):
        from core.code_agents.generators.registry import listar

        tipos = {g["tipo"] for g in listar()}
        expected = {
            "agent",
            "api",
            "tests",
            "scripts",
            "sql",
            "config",
            "monitor",
            "workflow",
            "parser",
            "repair",
        }
        assert tipos == expected


class TestGenerar:
    """generar(tipo, tarea) — generates code from a specific generator."""

    def test_invalid_tipo_returns_ok_false(self):
        from core.code_agents.generators.registry import generar

        result = generar("tipo_que_no_existe", "hacer algo")
        assert result["ok"] is False
        assert "error" in result

    def test_invalid_tipo_shows_available_generators(self):
        from core.code_agents.generators.registry import generar

        result = generar("inventado", "tarea")
        assert "Disponibles" in result["error"]

    def test_known_type_includes_modulo(self):
        from core.code_agents.generators.registry import GENERATORS

        for key in GENERATORS:
            assert "modulo" in GENERATORS[key], f"Missing 'modulo' in {key}"

    def test_known_type_includes_descripcion(self):
        from core.code_agents.generators.registry import GENERATORS

        for key in GENERATORS:
            assert "descripcion" in GENERATORS[key], f"Missing 'descripcion' in {key}"

    def test_all_generators_have_modelo(self):
        from core.code_agents.generators.registry import GENERATORS

        for key in GENERATORS:
            assert "modelo" in GENERATORS[key], f"Missing 'modelo' in {key}"
