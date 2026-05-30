#!/usr/bin/env python3
"""
URA Encryptor - Módulo de Cifrado para Configuración Sensible
Utiliza cryptography (Fernet) para cifrar valores sensibles en config.json y model_config.json
Guarda la llave maestra en el Llavero de macOS (Keychain) usando keyring
Cumple con estándares OWASP para protección de datos en reposo
"""

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

try:
    import base64

    from cryptography.fernet import Fernet

    CRYPTOGRAPHY_AVAILABLE = True
except ImportError:
    CRYPTOGRAPHY_AVAILABLE = False
    logger.warning("Cryptography no disponible. Instala con: pip install cryptography")

try:
    import keyring

    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False
    logger.warning("Keyring no disponible. Instala con: pip install keyring")


class Encryptor:
    """
    Sistema de cifrado para valores sensibles de configuración
    Usa keyring para guardar la llave maestra en el Llavero de macOS (Keychain)
    """

    def __init__(self, use_keyring: bool = True, key_path: str | None = None):
        """
        Inicializa el encryptor

        Args:
            use_keyring: Si True, usa keyring de macOS. Si False, usa archivo.
            key_path: Ruta del archivo de clave maestra (solo si use_keyring=False)
        """
        if not CRYPTOGRAPHY_AVAILABLE:
            raise RuntimeError("Cryptography no está instalado. Ejecuta: pip install cryptography")

        self.use_keyring = use_keyring and KEYRING_AVAILABLE
        self.keyring_service = "ura_encryption"
        self.keyring_username = "master_key"

        if self.use_keyring:
            logger.info("Encryptor usando keyring de macOS (Keychain)")
            self.fernet = self._load_or_create_key_keyring()
        else:
            if key_path is None:
                home_dir = Path.home()
                key_path = home_dir / ".ura.key"
            self.key_path = Path(key_path)
            logger.info(f"Encryptor usando archivo: {self.key_path}")
            self.fernet = self._load_or_create_key_file()

    def _load_or_create_key_file(self) -> Fernet:
        """
        Carga una clave existente de archivo o crea una nueva (método de respaldo)

        Returns:
            Instancia de Fernet con la clave
        """
        if self.key_path.exists():
            try:
                with open(self.key_path, "rb") as f:
                    key = f.read()
                return Fernet(key)
            except Exception as e:
                logger.error(f"Error cargando clave de archivo: {e}")
                return self._create_new_key_file()
        else:
            return self._create_new_key_file()

    def _create_new_key_file(self) -> Fernet:
        """
        Crea una nueva clave Fernet y la guarda en archivo (método de respaldo)

        Returns:
            Instancia de Fernet con la nueva clave
        """
        key = Fernet.generate_key()

        try:
            with open(self.key_path, "wb") as f:
                f.write(key)
            logger.info(f"Nueva clave creada en archivo: {self.key_path}")
        except Exception as e:
            logger.error(f"Error guardando clave en archivo: {e}")

        return Fernet(key)

    def _load_or_create_key_keyring(self) -> Fernet:
        """
        Carga una clave existente del keyring o crea una nueva

        Returns:
            Instancia de Fernet con la clave
        """
        try:
            # Intentar cargar clave existente del keyring
            key_bytes = keyring.get_password(self.keyring_service, self.keyring_username)
            if key_bytes:
                logger.info("Clave cargada del Keychain de macOS")
                return Fernet(key_bytes.encode())
        except Exception as e:
            logger.warning(f"Error cargando clave del keyring: {e}")

        # Crear nueva clave y guardarla en keyring
        return self._create_new_key_keyring()

    def _create_new_key_keyring(self) -> Fernet:
        """
        Crea una nueva clave Fernet y la guarda en el keyring de macOS

        Returns:
            Instancia de Fernet con la nueva clave
        """
        key = Fernet.generate_key()
        key_str = key.decode("utf-8")

        try:
            keyring.set_password(self.keyring_service, self.keyring_username, key_str)
            logger.info(
                "Nueva clave guardada en Keychain de macOS (requiere verificación del sistema)"
            )
        except Exception as e:
            logger.error(f"Error guardando clave en keyring: {e}")
            logger.warning("Fallback a archivo...")
            # Fallback a archivo si keyring falla
            self.use_keyring = False
            home_dir = Path.home()
            self.key_path = home_dir / ".ura.key"
            return self._create_new_key_file()

        return Fernet(key)

    def encrypt(self, value: str) -> str:
        """
        Cifra un valor de texto

        Args:
            value: Texto a cifrar

        Returns:
            Valor cifrado en base64
        """
        if not value:
            return value

        try:
            encrypted = self.fernet.encrypt(value.encode())
            return base64.b64encode(encrypted).decode()
        except Exception as e:
            logger.error(f"Error cifrando valor: {e}")
            return value

    def decrypt(self, encrypted_value: str) -> str:
        """
        Descifra un valor

        Args:
            encrypted_value: Valor cifrado en base64

        Returns:
            Texto descifrado
        """
        if not encrypted_value:
            return encrypted_value

        try:
            encrypted_bytes = base64.b64decode(encrypted_value.encode())
            decrypted = self.fernet.decrypt(encrypted_bytes)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Error descifrando valor: {e}")
            return encrypted_value

    def encrypt_dict(
        self, data: dict[str, Any], sensitive_keys: list | None = None
    ) -> dict[str, Any]:
        """
        Cifra valores sensibles en un diccionario

        Args:
            data: Diccionario con datos
            sensitive_keys: Lista de claves sensibles a cifrar

        Returns:
            Diccionario con valores sensibles cifrados
        """
        if sensitive_keys is None:
            # Claves sensibles por defecto
            sensitive_keys = [
                "password",
                "api_key",
                "secret",
                "token",
                "key",
                "private_key",
                "secret_key",
                "access_token",
                "refresh_token",
                "client_secret",
                "auth_token",
                "bearer_token",
            ]

        encrypted_data = data.copy()

        for key, value in encrypted_data.items():
            # Verificar si la clave es sensible
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                if isinstance(value, str):
                    encrypted_data[key] = self.encrypt(value)
                    logger.debug(f"Cifrado valor para clave: {key}")

        return encrypted_data

    def decrypt_dict(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Descifra valores en un diccionario

        Args:
            data: Diccionario con valores cifrados

        Returns:
            Diccionario con valores descifrados
        """
        decrypted_data = data.copy()

        for key, value in decrypted_data.items():
            if isinstance(value, str):
                try:
                    # Intentar descifrar
                    decrypted_data[key] = self.decrypt(value)
                    logger.debug(f"Descifrado valor para clave: {key}")
                except Exception as e:
                    logger.warning(f"Error silencioso en encryptor.decrypt_dict: {e}")
                    # fallback: mantener valor original sin descifrar

        return decrypted_data

    def encrypt_file(self, file_path: Path, sensitive_keys: list | None = None) -> bool:
        """
        Cifra valores sensibles en un archivo JSON

        Args:
            file_path: Ruta del archivo JSON
            sensitive_keys: Lista de claves sensibles

        Returns:
            True si se cifró correctamente
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            encrypted_data = self.encrypt_dict(data, sensitive_keys)

            # Guardar versión cifrada
            backup_path = file_path.with_suffix(".json.backup")
            with open(backup_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(encrypted_data, f, indent=2)

            logger.info(f"Archivo cifrado: {file_path} (backup: {backup_path})")
            return True
        except Exception as e:
            logger.error(f"Error cifrando archivo {file_path}: {e}")
            return False

    def decrypt_file(self, file_path: Path) -> dict[str, Any] | None:
        """
        Descifra un archivo JSON

        Args:
            file_path: Ruta del archivo JSON cifrado

        Returns:
            Diccionario descifrado o None si falla
        """
        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            decrypted_data = self.decrypt_dict(data)
            return decrypted_data
        except Exception as e:
            logger.error(f"Error descifrando archivo {file_path}: {e}")
            return None


# Singleton
_encryptor_instance = None


def get_encryptor(use_keyring: bool = True, key_path: str | None = None) -> Encryptor:
    """
    Obtiene la instancia singleton del Encryptor

    Args:
        use_keyring: Si True, usa keyring de macOS. Si False, usa archivo.
        key_path: Ruta opcional del archivo de clave (solo si use_keyring=False)

    Returns:
        Instancia de Encryptor
    """
    global _encryptor_instance
    if _encryptor_instance is None:
        _encryptor_instance = Encryptor(use_keyring=use_keyring, key_path=key_path)
    return _encryptor_instance


# Funciones de conveniencia para uso directo
def encrypt_config(config_path: str, sensitive_keys: list | None = None) -> bool:
    """
    Cifra un archivo de configuración

    Args:
        config_path: Ruta del archivo de configuración
        sensitive_keys: Lista de claves sensibles

    Returns:
        True si se cifró correctamente
    """
    encryptor = get_encryptor()
    return encryptor.encrypt_file(Path(config_path), sensitive_keys)


def decrypt_config(config_path: str) -> dict[str, Any] | None:
    """
    Descifra un archivo de configuración

    Args:
        config_path: Ruta del archivo de configuración

    Returns:
        Diccionario descifrado o None si falla
    """
    encryptor = get_encryptor()
    return encryptor.decrypt_file(Path(config_path))
