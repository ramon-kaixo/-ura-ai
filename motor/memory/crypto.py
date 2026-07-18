"""Cifrado opcional para persistencia de F26.

Usa AES-256-CTR con clave derivada vía PBKDF2.
Requiere: pip install cryptography

Si cryptography no está instalado, opera en modo texto plano.
"""

from __future__ import annotations

import hashlib
import os

_ENCRYPTION_ENABLED = False

try:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    _ENCRYPTION_ENABLED = True
except ImportError:
    pass


def _derive_key(key: str, salt: bytes) -> bytes | None:
    if not _ENCRYPTION_ENABLED:
        return None
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=100000)
    return kdf.derive(key.encode())


def encrypt(plaintext: bytes, key: str = "") -> bytes:
    """Cifra datos con AES-256-CTR. Si no hay key o cryptography, devuelve plaintext."""
    if not key or not _ENCRYPTION_ENABLED:
        return plaintext
    derived = _derive_key(key, b"urasalt2026")
    if derived is None:
        return plaintext
    nonce = b"\x00" * 16
    cipher = Cipher(algorithms.AES(derived), modes.CTR(nonce))
    encryptor = cipher.encryptor()
    return encryptor.update(plaintext) + encryptor.finalize()


def decrypt(ciphertext: bytes, key: str = "") -> bytes:
    """Descifra datos. Si no hay key o cryptography, devuelve ciphertext."""
    if not key or not _ENCRYPTION_ENABLED:
        return ciphertext
    derived = _derive_key(key, b"urasalt2026")
    if derived is None:
        return ciphertext
    nonce = b"\x00" * 16
    cipher = Cipher(algorithms.AES(derived), modes.CTR(nonce))
    decryptor = cipher.decryptor()
    return decryptor.update(ciphertext) + decryptor.finalize()


def is_encryption_available() -> bool:
    return _ENCRYPTION_ENABLED
