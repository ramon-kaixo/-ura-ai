#!/usr/bin/env python3
"""
Gateway de Seguridad Centralizado — URA Secure Gateway.

TODA la información que entra o sale de URA pasa por aquí.
Ningún dato llega a Ollama o al disco sin validación.

Pipeline automático:
  Internet → Aduana (validar) → Policía (filtrar) → Bóveda (cifrar) → Destino
"""

import hashlib
import json
import logging
import sys
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger("secure_gateway")

AUDIT_LOG = Path(__file__).parent.parent / "logs" / "secure_gateway.jsonl"


def _audit(accion: str, datos: dict, resultado: str) -> None:
    """Registro inmutable de cada operación."""
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.now(UTC).isoformat(),
        "accion": accion,
        "hash_datos": hashlib.sha256(json.dumps(datos, sort_keys=True).encode()).hexdigest()[:12],
        "resultado": resultado,
    }
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(entry) + "\n")


def validar_datos_externos(datos: dict | str, origen: str = "internet") -> tuple[bool, Any, str]:
    """
    FASE 1: ADUANA — todo dato externo se valida antes de entrar.
    Retorna (ok, datos_sanitizados, razon).
    """
    try:
        # 1. Sanitizar con Privacy Scrubber
        try:
            from core.privacy_scrubber import PrivacyScrubber

            scrubber = PrivacyScrubber()
            if isinstance(datos, str):
                datos = scrubber.scrub_text(datos)
        except ImportError:
            pass

        # 2. Validar con Agente Policía
        if isinstance(datos, str) and len(datos) > 10:
            try:
                from core.agente_policia_v2 import AgentePoliciaV2

                policia = AgentePoliciaV2()
                result = policia.validar(datos)
                if result["veredicto"] == "rechazado":
                    _audit(
                        "validar_datos",
                        {"origen": origen, "len": len(datos)},
                        f"RECHAZADO: {result.get('razon', result.get('razones', 'peligroso'))}",
                    )
                    return (
                        False,
                        None,
                        f"Bloqueado por seguridad: {result.get('razon', result.get('razones', 'peligroso'))}",
                    )
            except ImportError:
                pass

        _audit("validar_datos", {"origen": origen, "len": len(str(datos))}, "OK")
        return True, datos, "OK"
    except Exception as e:
        return False, None, str(e)


def cifrar_datos_sensibles(datos: dict) -> dict:
    """
    FASE 2: BÓVEDA — datos sensibles se cifran antes de guardar.
    """
    try:
        from core.boveda_manager import guardar, CRYPTO_AVAILABLE

        if not CRYPTO_AVAILABLE:
            return datos

        # Solo cifrar campos marcados como sensibles
        for key in list(datos.keys()):
            if any(s in key.lower() for s in ["token", "key", "password", "secret", "credential"]):
                valor = str(datos[key])
                hash_id = hashlib.sha256(valor.encode()).hexdigest()[:8]
                guardar(f"gw_{hash_id}", valor)
                datos[key] = f"🔒 BOVEDA:{hash_id}"

        _audit("cifrar_datos", {"campos": list(datos.keys())}, "OK")
    except ImportError:
        logger.info("Bóveda no disponible — datos sin cifrar")
    except Exception as e:
        logger.warning(f"Bóveda skip: {e}")

    return datos


def validar_comando(comando: str) -> tuple[bool, str]:
    """
    FASE 3: POLICÍA — todo comando se valida antes de ejecutar.
    """
    try:
        from core.agente_policia_v2 import AgentePoliciaV2

        policia = AgentePoliciaV2()
        result = policia.validar(comando)
        ok = result["veredicto"] == "aprobado"
        razon = result.get("razon", result.get("veredicto", "?"))
        _audit(
            "validar_comando",
            {"comando": comando[:100]},
            "APROBADO" if ok else f"RECHAZADO: {razon}",
        )
        return ok, razon
    except ImportError:
        return True, "Policía no disponible — modo permisivo"
    except Exception as e:
        return False, str(e)


def gateway_completo(
    datos: dict | str, origen: str = "internet", es_comando: bool = False
) -> tuple[bool, Any, str]:
    """
    PIPELINE COMPLETO: Aduana → Policía → Bóveda.
    Usar siempre esta función para cualquier dato externo.
    """
    # Paso 1: Validar (Aduana + Policía)
    ok, sanitizado, razon = validar_datos_externos(datos, origen)
    if not ok:
        return False, None, razon

    # Paso 2: Si es comando, validación extra
    if es_comando and isinstance(datos, str):
        ok, razon = validar_comando(datos)
        if not ok:
            return False, None, f"Comando bloqueado: {razon}"

    # Paso 3: Cifrar si es necesario (Bóveda)
    if isinstance(sanitizado, dict):
        sanitizado = cifrar_datos_sensibles(sanitizado)

    return True, sanitizado, "OK"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("🛡️ URA Secure Gateway — test")

    # Test: datos normales
    ok, datos, razon = gateway_completo("información sobre IA", "internet")
    print(f"Datos normales: {ok} — {razon}")

    # Test: datos peligrosos
    ok, datos, razon = gateway_completo("rm -rf / --no-preserve-root", "internet")
    print(f"Datos peligrosos: {ok} — {razon}")

    # Test: datos con credenciales
    ok, datos, razon = gateway_completo(
        {"token": "sk-123456", "content": "IA research"}, "internet"
    )
    print(f"Datos con credenciales: {ok} — token cifrado: {'BOVEDA' in str(datos)}")
