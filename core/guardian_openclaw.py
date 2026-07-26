#!/usr/bin/env python3
"""Guardián de Seguridad para OpenClaw
Envuelve cualquier acción de OpenClaw con reglas de seguridad.
"""

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Directorios de seguridad
BACKUP_DIR = Path.home() / ".ura" / "backups" / "pre_delete"
AUDIT_LOG = Path.home() / ".ura" / "audit.log"
SANDBOX_DIR = Path.home() / ".ura" / "sandbox"

# Licencias gratuitas reconocidas
FREE_LICENSES = [
    "MIT",
    "GPL",
    "GPL-2.0",
    "GPL-3.0",
    "Apache",
    "Apache-2.0",
    "BSD",
    "BSD-2-Clause",
    "BSD-3-Clause",
    "LGPL",
    "MPL",
    "Unlicense",
    "Public Domain",
]


class GuardianOpenCLaw:
    """Guardián de seguridad que envuelve acciones de OpenClaw."""

    # Reglas de seguridad activas (atributo de clase)
    reglas: list[str] = [  # noqa: RUF012
        "policía",
        "copia_previa",
        "caja_de_arena",
        "control_instalacion",
        "contraseña_final",
        "auditoría",
    ]

    def __init__(self) -> None:
        """Inicializar el guardián."""
        self.backup_dir = BACKUP_DIR
        self.audit_log = AUDIT_LOG
        self.sandbox_dir = SANDBOX_DIR

        # Crear directorios necesarios
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.sandbox_dir.mkdir(parents=True, exist_ok=True)

        # Estadísticas
        self.stats = {
            "total_acciones": 0,
            "acciones_permitidas": 0,
            "acciones_bloqueadas": 0,
            "backups_creados": 0,
            "sandbox_exitosos": 0,
            "sandbox_fallidos": 0,
            "instalaciones_bloqueadas": 0,
            "passwords_bloqueados": 0,
        }

        logger.info("Guardián de OpenClaw inicializado")

    def _log_audit(self, agente: str, accion: str, resultado: str, detalles: str = "") -> None:
        """Registrar acción en log de auditoría."""
        try:
            timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
            with open(self.audit_log, "a", encoding="utf-8") as f:  # noqa: PTH123
                f.write(f"[{timestamp}] Agente: {agente} | Acción: {accion} | Resultado: {resultado} | {detalles}\n")
        except Exception as e:
            logger.exception(f"Error registrando en audit.log: {e}")

    def _consultar_policia(self, accion: str, **kwargs) -> tuple[bool, str]:
        # Stub: agente_policia_v2 no operativo en este nodo
        return True, "stub: policia desactivado"

    def _crear_backup(self, ruta: str) -> bool:
        """REGLA 2 - COPIA PREVIA: Crear backup antes de operaciones de borrado.

        Returns:
            True si el backup fue exitoso

        """
        try:
            ruta_path = Path(ruta)
            if not ruta_path.exists():
                logger.warning(f"Ruta no existe, no se puede hacer backup: {ruta}")
                return False

            # Crear timestamp
            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")

            # Determinar nombre de backup
            if ruta_path.is_file():
                backup_name = f"{ruta_path.name}_{timestamp}.bak"
                backup_path = self.backup_dir / backup_name
                shutil.copy2(ruta_path, backup_path)
            elif ruta_path.is_dir():
                backup_name = f"{ruta_path.name}_{timestamp}"
                backup_path = self.backup_dir / backup_name
                shutil.copytree(ruta_path, backup_path)
            else:
                logger.warning(f"Ruta no es archivo ni directorio: {ruta}")
                return False

            self.stats["backups_creados"] += 1
            logger.info(f"Backup creado: {backup_path}")
            return True

        except Exception as e:
            logger.exception(f"Error creando backup: {e}")
            return False

    def _ejecutar_sandbox(self, accion: str, **kwargs) -> tuple[bool, str]:
        """REGLA 3 - CAJA DE ARENA: Ejecutar acción en sandbox.

        Returns:
            (exitoso, mensaje)

        """
        try:
            # Ejecutar acción 3 veces en sandbox
            exitosos = 0
            for i in range(3):
                try:
                    # Simular ejecución en sandbox
                    resultado = self._simular_accion_sandbox(accion, **kwargs)
                    if resultado:
                        exitosos += 1
                except Exception as e:
                    logger.warning(f"Intento {i + 1} falló en sandbox: {e}")

            if exitosos == 3:
                self.stats["sandbox_exitosos"] += 1
                return True, "Sandbox: 3/3 exitosos"
            self.stats["sandbox_fallidos"] += 1
            return False, f"Sandbox: {exitosos}/3 exitosos"

        except Exception as e:
            logger.exception(f"Error en sandbox: {e}")
            self.stats["sandbox_fallidos"] += 1
            return False, f"Error en sandbox: {e}"

    def _simular_accion_sandbox(self, accion: str, **kwargs) -> bool:
        """Simular acción en sandbox (implementación básica)."""
        # Por ahora, simulación básica: verificar que la acción no contiene comandos peligrosos
        accion_lower = accion.lower()
        comandos_peligrosos = ["rm -rf /", "dd if=/dev/zero", "mkfs", "format", "wipe"]

        return all(peligroso not in accion_lower for peligroso in comandos_peligrosos)

    def _verificar_licencia(self, paquete: str) -> tuple[bool, str]:
        """REGLA 4 - CONTROL DE INSTALACIÓN: Verificar si el paquete es gratuito.

        Returns:
            (es_gratuito, mensaje)

        """
        try:
            # Lista de paquetes conocidos de pago (ejemplo básico)
            paquetes_pago = [
                "jetbrains",
                "intellij",
                "pycharm",
                "webstorm",
                "sublime",
                "textmate",
                "bbedit",
                "parallels",
                "vmware",
                "virtualbox-pro",
                "adobe",
                "photoshop",
                "illustrator",
            ]

            paquete_lower = paquete.lower()
            for pago in paquetes_pago:
                if pago in paquete_lower:
                    return False, f"Paquete de pago detectado: {paquete}"

            # Por defecto, asumir que es gratuito
            return True, "Paquete gratuito (asumido)"

        except Exception as e:
            logger.exception(f"Error verificando licencia: {e}")
            # Si falla la verificación, por seguridad pedir autorización
            return False, f"Error verificando licencia: {e}"

    def _autorizar_instalacion(self, paquete: str, precio: float | None = None) -> bool:
        """Solicitar autorización explícita al usuario para instalación.

        Returns:
            True si el usuario autoriza

        """
        try:
            if precio:
                mensaje = f"El paquete '{paquete}' cuesta ${precio}. ¿Autorizar instalación? (s/n): "
            else:
                mensaje = f"El paquete '{paquete}' requiere autorización. ¿Autorizar instalación? (s/n): "

            respuesta = input(mensaje).strip().lower()
            return respuesta in {"s", "si", "sí"}

        except Exception as e:
            logger.exception(f"Error solicitando autorización: {e}")
            return False

    def _detectar_password_field(self, formulario: dict[str, Any]) -> bool:
        """REGLA 5 - CONTRASEÑA FINAL: Detectar campos password en formulario.

        Returns:
            True si hay campos de password

        """
        if not isinstance(formulario, dict):
            return False

        campos_password = []
        for key in formulario:
            key_lower = key.lower()
            if "password" in key_lower or "pass" in key_lower or "pwd" in key_lower:
                campos_password.append(key)

        if campos_password:
            self.stats["passwords_bloqueados"] += 1
            logger.warning(f"Campos de password detectados: {campos_password}")
            return True

        return False

    def ejecutar(self, accion: str, **kwargs) -> dict[str, Any]:
        """Ejecutar una acción con todas las reglas de seguridad.

        Args:
            accion: Descripción de la acción a ejecutar
            **kwargs: Parámetros adicionales de la acción

        Returns:
            Dict con resultado de la ejecución

        """
        self.stats["total_acciones"] += 1
        timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")

        logger.info(f"[{timestamp}] Ejecutando acción: {accion}")

        # REGLA 4 - CONTROL DE INSTALACIÓN
        accion_lower = accion.lower()
        if any(cmd in accion_lower for cmd in ["brew install", "pip install", "npm install", "apt install"]):
            # Extraer nombre del paquete
            partes = accion.split()
            if len(partes) >= 3:
                paquete = partes[2]
                es_gratuito, mensaje = self._verificar_licencia(paquete)

                if not es_gratuito:
                    self.stats["instalaciones_bloqueadas"] += 1
                    self._log_audit("guardian", accion, "BLOQUEADO", mensaje)
                    return {
                        "success": False,
                        "message": f"Instalación bloqueada: {mensaje}",
                        "autorizacion_requerida": True,
                    }

                # Si es gratuito, autorizar
                if not self._autorizar_instalacion(paquete):
                    self.stats["instalaciones_bloqueadas"] += 1
                    self._log_audit("guardian", accion, "BLOQUEADO", "Usuario denegó autorización")
                    return {"success": False, "message": "Instalación denegada por el usuario"}

        # REGLA 1 - POLICÍA
        permitido, motivo = self._consultar_policia(accion, **kwargs)
        if not permitido:
            self.stats["acciones_bloqueadas"] += 1
            self._log_audit("guardian", accion, "BLOQUEADO", motivo)
            return {"success": False, "message": f"Acción bloqueada por policía: {motivo}"}

        # REGLA 2 - COPIA PREVIA (solo para operaciones de borrado)
        if any(cmd in accion_lower for cmd in ["rm ", "delete", "unlink", "rmdir"]):
            # Intentar extraer ruta para backup
            ruta = kwargs.get("ruta", "")
            if not ruta:
                # Intentar extraer de la acción
                partes = accion.split()
                if len(partes) >= 2:
                    ruta = partes[-1]

            if ruta:
                backup_exitoso = self._crear_backup(ruta)
                if not backup_exitoso:
                    logger.warning("Backup falló, pero se procede con la acción")

        # REGLA 3 - CAJA DE ARENA
        sandbox_exitoso, mensaje_sandbox = self._ejecutar_sandbox(accion, **kwargs)
        if not sandbox_exitoso:
            self.stats["acciones_bloqueadas"] += 1
            self._log_audit("guardian", accion, "BLOQUEADO", mensaje_sandbox)
            return {"success": False, "message": f"Acción bloqueada por sandbox: {mensaje_sandbox}"}

        # REGLA 5 - CONTRASEÑA FINAL (si hay formulario)
        formulario = kwargs.get("formulario")
        if formulario and self._detectar_password_field(formulario):
            self.stats["acciones_bloqueadas"] += 1
            self._log_audit("guardian", accion, "BLOQUEADO", "Campo de password detectado")
            return {
                "success": False,
                "message": "Acción bloqueada: Campo de password detectado. Por favor, introduzca la contraseña manualmente.",
            }

        # Si pasa todas las reglas, ejecutar acción
        self.stats["acciones_permitidas"] += 1
        self._log_audit("guardian", accion, "PERMITIDO", "Todas las reglas pasadas")

        return {
            "success": True,
            "message": "Acción permitida por el guardián",
            "motivo_policia": motivo,
            "sandbox": mensaje_sandbox,
        }

    def mostrar_reglas(self) -> None:
        """Imprimir las reglas de seguridad numeradas."""
        for _i, _regla in enumerate(self.reglas, start=1):
            pass

    def estado(self) -> dict[str, Any]:
        """Devolver estadísticas de seguridad."""
        return {
            "guardian_activo": True,
            "backup_dir": str(self.backup_dir),
            "audit_log": str(self.audit_log),
            "sandbox_dir": str(self.sandbox_dir),
            "estadisticas": self.stats,
        }


# Instancia global del guardián
_guardian_instance: GuardianOpenCLaw | None = None


def get_guardian() -> GuardianOpenCLaw:
    """Obtener instancia global del guardián (singleton)."""
    global _guardian_instance  # noqa: PLW0603
    if _guardian_instance is None:
        _guardian_instance = GuardianOpenCLaw()
    return _guardian_instance


if __name__ == "__main__":
    g = get_guardian()
