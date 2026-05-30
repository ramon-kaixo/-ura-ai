#!/usr/bin/env python3
"""
core/boveda_manager.py - Bóveda cifrada para secretos de URA
Usa Fernet (AES-128-CBC) para cifrar/descifrar valores sensibles.
"""

import json
import logging
import stat
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from cryptography.fernet import Fernet

    CRYPTO_AVAILABLE = True
except ImportError:
    CRYPTO_AVAILABLE = False
    logger.warning("cryptography no instalada — Bóveda desactivada")


_KEY_FILE = Path(__file__).parent.parent / ".boveda_key"
_INDEX_FILE = Path(__file__).parent.parent / "sandbox" / "Boveda" / "indice.db"


def _get_or_create_key() -> bytes:
    """Obtener o crear clave Fernet, protegida con chmod 600."""
    if _KEY_FILE.exists():
        return _KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _KEY_FILE.write_bytes(key)
    _KEY_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)  # 600
    logger.info("Nueva clave de Bóveda creada en %s", _KEY_FILE)
    return key


def _get_fernet() -> "Fernet":
    if not CRYPTO_AVAILABLE:
        raise RuntimeError("cryptography no instalada — instala con: pip install cryptography")
    return Fernet(_get_or_create_key())


def _load_index() -> dict:
    if _INDEX_FILE.exists():
        try:
            return json.loads(_INDEX_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_index(index: dict) -> None:
    _INDEX_FILE.parent.mkdir(parents=True, exist_ok=True)
    _INDEX_FILE.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


def guardar(nombre: str, valor: str) -> None:
    """Cifrar y guardar un secreto en la Bóveda."""
    f = _get_fernet()
    token = f.encrypt(valor.encode()).decode()
    index = _load_index()
    index[nombre] = token
    _save_index(index)
    logger.info("Secreto '%s' guardado en Bóveda", nombre)


def recuperar(nombre: str) -> str | None:
    """Descifrar y recuperar un secreto de la Bóveda."""
    f = _get_fernet()
    index = _load_index()
    if nombre not in index:
        logger.warning("Secreto '%s' no encontrado en Bóveda", nombre)
        return None
    try:
        return f.decrypt(index[nombre].encode()).decode()
    except Exception as e:
        logger.error("Error descifrando '%s': %s", nombre, e)
        return None


def eliminar(nombre: str) -> bool:
    """Eliminar un secreto de la Bóveda."""
    index = _load_index()
    if nombre in index:
        del index[nombre]
        _save_index(index)
        logger.info("Secreto '%s' eliminado de Bóveda", nombre)
        return True
    return False


def listar() -> list[str]:
    """Listar nombres de secretos guardados (sin valores)."""
    return list(_load_index().keys())


def verificar_integridad() -> dict:
    """Verificar que todos los secretos se pueden descifrar."""
    f = _get_fernet()
    index = _load_index()
    resultado = {"total": len(index), "ok": 0, "errores": []}
    for nombre, token in index.items():
        try:
            f.decrypt(token.encode())
            resultado["ok"] += 1
        except Exception:
            resultado["errores"].append(nombre)
    return resultado


if __name__ == "__main__":
    print("=== Test Bóveda ===")
    guardar("test_api_key", "mi_secreto_123")
    valor = recuperar("test_api_key")
    print(f"Recuperado: {valor}")
    print(f"Secretos: {listar()}")
    print(f"Integridad: {verificar_integridad()}")
    eliminar("test_api_key")
    print(f"Tras eliminar: {listar()}")
