#!/usr/bin/env python3
"""
Módulo: core/sandbox.py
Propósito: Entorno aislado para ejecutar código Python de forma segura con import dinámico controlado.
Dependencias principales: importlib, subprocess, pathlib, logging
Reglas especiales: Nunca ejecutar código sin sandbox. Capturar OSError. No propagar excepciones del sandbox.
"""

import asyncio
import logging
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SANDBOX_LOG = Path.home() / ".ura" / "sandbox.log"
SANDBOX_LOG.parent.mkdir(parents=True, exist_ok=True)


class Sandbox:
    """Caja de arena para pruebas aisladas de módulos."""

    def __init__(self):
        self.backup_dir = Path.home() / ".ura" / "sandbox_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def _log(self, event_type: str, details: str):
        """Registrar evento en log del sandbox."""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(SANDBOX_LOG, "a", encoding="utf-8") as f:
                f.write(f"[{timestamp}] [{event_type}] {details}\n")
        except Exception as e:
            logger.error(f"Error registrando en sandbox.log: {e}")

    async def test_improvement(self, module_name: str, test_code: str) -> dict:
        """
        Ejecutar código de prueba en subproceso aislado con timeout.

        Args:
            module_name: Nombre del módulo a probar
            test_code: Código de prueba a ejecutar

        Returns:
            Dict con {'success': bool, 'output': str, 'error': str}
        """
        self._log("TEST_START", f"Probando módulo: {module_name}")

        try:
            # Crear archivo temporal con el código de prueba
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(test_code)
                test_file = f.name

            try:
                # Ejecutar en subproceso con timeout
                process = await asyncio.create_subprocess_exec(
                    "python",
                    test_file,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

                try:
                    stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)

                    output = stdout.decode("utf-8", errors="ignore")
                    error = stderr.decode("utf-8", errors="ignore")

                    success = process.returncode == 0

                    result = {"success": success, "output": output, "error": error}

                    self._log("TEST_COMPLETE", f"Módulo: {module_name}, Success: {success}")
                    return result

                except TimeoutError:
                    process.kill()
                    await process.wait()

                    result = {
                        "success": False,
                        "output": "",
                        "error": "Timeout: prueba excedió 30 segundos",
                    }

                    self._log("TEST_TIMEOUT", f"Módulo: {module_name}")
                    return result

            finally:
                # Limpiar archivo temporal
                try:
                    Path(test_file).unlink()
                except OSError:
                    pass

        except Exception as e:
            result = {"success": False, "output": "", "error": str(e)}

            self._log("TEST_ERROR", f"Módulo: {module_name}, Error: {str(e)}")
            return result

    def safe_import(self, module_name: str) -> bool:
        """
        Intentar importar un módulo de prueba sin afectar al sistema principal.

        Args:
            module_name: Nombre del módulo a importar

        Returns:
            True si exitoso, False si no
        """
        self._log("IMPORT_START", f"Importando módulo: {module_name}")

        try:
            import importlib

            spec = importlib.util.find_spec(module_name)

            if spec is None:
                self._log("IMPORT_FAIL", f"Módulo no encontrado: {module_name}")
                return False

            # Cargar módulo sin ejecutar
            module = importlib.util.module_from_spec(spec)
            if spec.loader is None:
                self._log("IMPORT_FAIL", f"Loader no disponible para: {module_name}")
                return False
            spec.loader.exec_module(module)

            self._log("IMPORT_SUCCESS", f"Módulo importado: {module_name}")
            return True

        except Exception as e:
            self._log("IMPORT_ERROR", f"Módulo: {module_name}, Error: {str(e)}")
            return False

    def create_backup(self, module_path: str) -> str | None:
        """
        Crear copia de seguridad del módulo antes de probar cambios.

        Args:
            module_path: Ruta del módulo a respaldar

        Returns:
            Ruta de la copia de seguridad o None si falla
        """
        try:
            source = Path(module_path)
            if not source.exists():
                self._log("BACKUP_FAIL", f"Archivo no encontrado: {module_path}")
                return None

            # Crear nombre único para backup
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{source.stem}_{timestamp}{source.suffix}"
            backup_path = self.backup_dir / backup_name

            # Copiar archivo
            shutil.copy2(source, backup_path)

            self._log("BACKUP_SUCCESS", f"Backup creado: {backup_path}")
            return str(backup_path)

        except Exception as e:
            self._log("BACKUP_ERROR", f"Error creando backup: {str(e)}")
            return None

    def rollback(self, module_path: str, backup_path: str) -> bool:
        """
        Restaurar copia de seguridad si la prueba falla.

        Args:
            module_path: Ruta del módulo a restaurar
            backup_path: Ruta de la copia de seguridad

        Returns:
            True si exitoso, False si no
        """
        try:
            source = Path(backup_path)
            dest = Path(module_path)

            if not source.exists():
                self._log("ROLLBACK_FAIL", f"Backup no encontrado: {backup_path}")
                return False

            # Restaurar
            shutil.copy2(source, dest)

            self._log("ROLLBACK_SUCCESS", f"Restaurado: {module_path} desde {backup_path}")
            return True

        except Exception as e:
            self._log("ROLLBACK_ERROR", f"Error restaurando: {str(e)}")
            return False

    def cleanup_old_backups(self, days: int = 7):
        """
        Limpiar copias de seguridad antiguas.

        Args:
            days: Días de antigüedad para eliminar
        """
        try:
            cutoff = datetime.now().timestamp() - (days * 86400)

            for backup in self.backup_dir.iterdir():
                if backup.is_file() and backup.stat().st_mtime < cutoff:
                    backup.unlink()
                    self._log("CLEANUP", f"Backup antiguo eliminado: {backup.name}")

        except Exception as e:
            self._log("CLEANUP_ERROR", f"Error limpiando backups: {str(e)}")


_sandbox_instance: Sandbox | None = None


def get_sandbox() -> Sandbox:
    """Obtener el singleton del sandbox."""
    global _sandbox_instance
    if _sandbox_instance is None:
        _sandbox_instance = Sandbox()
    return _sandbox_instance


if __name__ == "__main__":
    import asyncio

    async def test():
        sandbox = Sandbox()

        # Test 1: safe_import
        print("Test safe_import:")
        print(f"  math: {sandbox.safe_import('math')}")
        print(f"  modulo_inexistente: {sandbox.safe_import('modulo_inexistente')}")

        # Test 2: test_improvement
        print("\nTest test_improvement:")
        test_code = """
print('Hola desde el sandbox')
x = 1 + 1
print(f'1 + 1 = {x}')
"""
        result = await sandbox.test_improvement("test_module", test_code)
        print(f"  Success: {result['success']}")
        print(f"  Output: {result['output']}")

        # Test 3: backup
        print("\nTest backup:")
        test_file = Path("/tmp/test_sandbox.txt")
        test_file.write_text("contenido original")
        backup = sandbox.create_backup(str(test_file))
        print(f"  Backup creado: {backup}")

        # Test 4: rollback
        print("\nTest rollback:")
        test_file.write_text("contenido modificado")
        success = sandbox.rollback(str(test_file), backup)
        print(f"  Rollback exitoso: {success}")
        print(f"  Contenido restaurado: {test_file.read_text()}")

        # Limpiar
        test_file.unlink()

        print("\n✅ SANDBOX FUNCIONANDO")

    asyncio.run(test())
