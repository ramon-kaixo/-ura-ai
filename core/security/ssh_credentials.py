#!/usr/bin/env python3
"""Secure SSH credential management using macOS Keychain."""

import getpass

try:
    import keyring
except ImportError:
    keyring = None

SERVICE_NAME = "URA_GX10_SSH"


def guardar_credenciales(usuario: str, password: str) -> None:
    """Stores SSH password in the system keyring.

    Args:
        usuario: SSH username.
        password: SSH password.
    """
    if keyring is None:
        raise ImportError("keyring not installed. Run: pip install keyring")
    keyring.set_password(SERVICE_NAME, usuario, password)


def obtener_credenciales(usuario: str) -> str | None:
    """Retrieves SSH password from the system keyring.

    Args:
        usuario: SSH username.

    Returns:
        Password string or None if not found.
    """
    if keyring is None:
        return None
    try:
        return keyring.get_password(SERVICE_NAME, usuario)
    except Exception:
        return None


def preguntar_y_guardar_si_no_existe(usuario: str) -> str | None:
    """Prompts for password if not stored, then saves it.

    Args:
        usuario: SSH username.

    Returns:
        Password string or None if cancelled.
    """
    pwd = obtener_credenciales(usuario)
    if not pwd:
        print(f"No hay contraseña para {usuario} en el llavero.")
        pwd = getpass.getpass(f"Introduce la contraseña SSH de {usuario}@GX10: ")
        if pwd:
            guardar_credenciales(usuario, pwd)
    return pwd


if __name__ == "__main__":
    import sys

    user = sys.argv[1] if len(sys.argv) > 1 else "root"
    result = preguntar_y_guardar_si_no_existe(user)
    if result:
        print(f"Credenciales guardadas para {user}")
