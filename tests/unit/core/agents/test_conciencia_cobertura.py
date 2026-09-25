#!/usr/bin/env python3
"""Cobertura 100x100 de motor/core/agents/conciencia.py."""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from motor.core.agents.conciencia import Conciencia


class TestConcienciaLeer:
    """Tests para Conciencia.leer()."""

    @pytest.mark.unit
    def test_leer_archivo_existente(self, tmp_path):
        """Leer archivo existente válido."""
        test_file = tmp_path / "conciencia.json"
        test_data = {"estado_general": "ok", "nivel_error": 0, "test": "data"}
        test_file.write_text(json.dumps(test_data))

        with patch.object(Conciencia, 'PATH', test_file):
            result = Conciencia.leer()
            assert result == test_data

    @pytest.mark.unit
    def test_leer_archivo_no_existe(self):
        """Archivo no existe -> retorna _nuevo()."""
        non_existent = Path("/tmp/no_existe_conciencia.json")
        with patch.object(Conciencia, 'PATH', non_existent):
            result = Conciencia.leer()
            assert "estado_general" in result
            assert result["estado_general"] == "ok"

    @pytest.mark.unit
    def test_leer_json_invalido(self, tmp_path):
        """JSON inválido -> retorna _nuevo()."""
        test_file = tmp_path / "conciencia.json"
        test_file.write_text("no es json valido")

        with patch.object(Conciencia, 'PATH', test_file):
            result = Conciencia.leer()
            assert "estado_general" in result
            assert result["estado_general"] == "ok"

    @pytest.mark.unit
    def test_leer_no_es_dict(self, tmp_path):
        """JSON no es dict -> retorna _nuevo()."""
        test_file = tmp_path / "conciencia.json"
        test_file.write_text('["no", "es", "dict"]')

        with patch.object(Conciencia, 'PATH', test_file):
            result = Conciencia.leer()
            assert "estado_general" in result
            assert result["estado_general"] == "ok"


class TestConcienciaNuevo:
    """Tests para Conciencia._nuevo()."""

    @pytest.mark.unit
    def test_nuevo_estructura_completa(self):
        """Verifica estructura completa del estado por defecto."""
        nuevo = Conciencia._nuevo()
        
        assert nuevo["estado_general"] == "ok"
        assert nuevo["nivel_error"] == 0
        assert "procesos" in nuevo
        assert "contexto_global" in nuevo
        
        # Verificar procesos
        assert "orquestador" in nuevo["procesos"]
        assert "ejecutor" in nuevo["procesos"]
        assert "reparador" in nuevo["procesos"]
        assert nuevo["procesos"]["orquestador"]["estado"] == "idle"
        
        # Verificar contexto_global
        assert nuevo["contexto_global"]["ciclo_actual"] == 0
        assert nuevo["contexto_global"]["progreso"] == "0/0"
        assert nuevo["contexto_global"]["errores_acumulados"] == []
        assert nuevo["contexto_global"]["arreglos_aplicados"] == []


class TestConcienciaEscribir:
    """Tests para Conciencia.escribir()."""

    @pytest.mark.unit
    def test_escribir_crea_archivo(self, tmp_path):
        """Verifica que crea archivo y escribe datos."""
        test_file = tmp_path / "conciencia.json"
        
        with patch.object(Conciencia, 'PATH', test_file):
            test_data = {"estado_general": "test", "nuevo": "valor"}
            Conciencia.escribir(test_data)
            
            assert test_file.exists()
            data = json.loads(test_file.read_text())
            assert data["estado_general"] == "test"
            assert data["nuevo"] == "valor"

    @pytest.mark.unit
    def test_escribir_crea_directorio(self, tmp_path):
        """Verifica que crea directorio padre si no existe."""
        nested = tmp_path / "nested" / "dir" / "conciencia.json"
        
        with patch.object(Conciencia, 'PATH', nested):
            Conciencia.escribir({"test": "data"})
            
            assert nested.exists()

    @pytest.mark.unit
    def test_escribir_atomico(self, tmp_path):
        """Verifica escritura atómica (usa .tmp y replace)."""
        test_file = tmp_path / "conciencia.json"
        
        with patch.object(Conciencia, 'PATH', test_file):
            Conciencia.escribir({"atomic": True})
            
            # No debe quedar archivo .tmp
            tmp_files = list(tmp_path.glob("*.tmp"))
            assert len(tmp_files) == 0


class TestConcienciaActualizarProceso:
    """Tests para Conciencia.actualizar_proceso()."""

    @pytest.mark.unit
    def test_actualizar_proceso_existente(self):
        """Actualiza estado de proceso existente."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            mock_leer.return_value = {
                "procesos": {"orquestador": {"estado": "idle"}}
            }
            
            Conciencia.actualizar_proceso("orquestador", "activo")
            
            mock_escribir.assert_called_once()
            args = mock_escribir.call_args[0][0]
            assert args["procesos"]["orquestador"]["estado"] == "activo"

    @pytest.mark.unit
    def test_actualizar_proceso_nuevo(self):
        """Añade nuevo proceso si no existe."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            mock_leer.return_value = {"procesos": {}}
            
            Conciencia.actualizar_proceso("nuevo_proceso", "nuevo_estado")
            
            args = mock_escribir.call_args[0][0]
            assert "nuevo_proceso" in args["procesos"]
            assert args["procesos"]["nuevo_proceso"]["estado"] == "nuevo_estado"

    @pytest.mark.unit
    def test_actualizar_proceso_ultima_actualizacion(self):
        """Verifica que añade ultima_actualizacion (no timestamp)."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            mock_leer.return_value = {"procesos": {}}
            
            Conciencia.actualizar_proceso("test", "estado")
            
            args = mock_escribir.call_args[0][0]
            assert "ultima_actualizacion" in args["procesos"]["test"]


class TestConcienciaRegistrarError:
    """Tests para Conciencia.registrar_error()."""

    @pytest.mark.unit
    def test_registrar_error_incrementa_nivel(self):
        """Verifica que incrementa nivel_error."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            mock_leer.return_value = {
                "nivel_error": 0,
                "contexto_global": {"errores_acumulados": []}
            }
            
            Conciencia.registrar_error(2, "test error")
            
            args = mock_escribir.call_args[0][0]
            assert args["nivel_error"] == 2
            assert len(args["contexto_global"]["errores_acumulados"]) == 1
            assert args["contexto_global"]["errores_acumulados"][0]["nivel"] == 2
            assert args["contexto_global"]["errores_acumulados"][0]["mensaje"] == "test error"

    @pytest.mark.unit
    def test_registrar_error_no_decrementa(self):
        """Verifica que no decrementa nivel si es menor."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            mock_leer.return_value = {
                "nivel_error": 3,
                "contexto_global": {"errores_acumulados": []}
            }
            
            Conciencia.registrar_error(1, "minor error")
            
            args = mock_escribir.call_args[0][0]
            assert args["nivel_error"] == 3  # No decrementa

    @pytest.mark.unit
    def test_registrar_error_limite_50(self):
        """Verifica límite de 50 errores acumulados."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            # Crear 51 errores
            errores = [{"nivel": 1, "mensaje": f"error {i}"} for i in range(51)]
            mock_leer.return_value = {
                "nivel_error": 0,
                "contexto_global": {"errores_acumulados": errores}
            }
            
            Conciencia.registrar_error(1, "nuevo error")
            
            args = mock_escribir.call_args[0][0]
            assert len(args["contexto_global"]["errores_acumulados"]) == 50


class TestConcienciaNivelError:
    """Tests para Conciencia.nivel_error()."""

    @pytest.mark.unit
    def test_nivel_error_retorna_int(self):
        """Retorna nivel_error como int."""
        with patch.object(Conciencia, 'leer') as mock_leer:
            mock_leer.return_value = {"nivel_error": 2}
            assert Conciencia.nivel_error() == 2

    @pytest.mark.unit
    def test_nivel_error_default_zero(self):
        """Retorna 0 si no existe."""
        with patch.object(Conciencia, 'leer') as mock_leer:
            mock_leer.return_value = {}
            assert Conciencia.nivel_error() == 0


class TestConcienciaThreadSafety:
    """Tests de thread-safety."""

    @pytest.mark.unit
    def test_lock_existe(self):
        """Verifica que existe lock de threading."""
        import threading
        assert hasattr(Conciencia, '_lock')
        assert isinstance(Conciencia._lock, type(threading.Lock()))


class TestConcienciaRegistrarErrorLimite:
    """Tests para límite de errores acumulados."""

    @pytest.mark.unit
    def test_limite_50_errores_recortado(self):
        """Verifica que recorta a 50 errores."""
        with patch.object(Conciencia, 'leer') as mock_leer, \
             patch.object(Conciencia, 'escribir') as mock_escribir:
            
            # 51 errores existentes
            errores = [{"nivel": 1, "mensaje": f"error {i}"} for i in range(51)]
            mock_leer.return_value = {
                "nivel_error": 0,
                "contexto_global": {"errores_acumulados": errores}
            }
            
            Conciencia.registrar_error(1, "nuevo")
            
            args = mock_escribir.call_args[0][0]
            assert len(args["contexto_global"]["errores_acumulados"]) == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
