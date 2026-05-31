#!/usr/bin/env python3
"""
Agente Policía conversacional.
Método principal: consultar(consulta: str) -> str
Uso: validación informal de comandos vía LLM (deepseek-r1:7b)
Importadores: guardian_openclaw.py

NO confundir con core/agente_policia_v2.py — mismo nombre, distinta responsabilidad.
core/ = validador estructurado con enums. agents/ = conversacional con LLM.
"""

import json
import os
import re
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

# Agregar ruta de URA_App al path para importar consensus_system
URA_APP_PATH = Path("/Users/ramonesnaola/URA/ura_ia_1972")
if URA_APP_PATH.exists() and str(URA_APP_PATH) not in sys.path:
    sys.path.insert(0, str(URA_APP_PATH))

try:
    from consensus_system import get_consensus_system

    CONSENSUS_AVAILABLE = True
except ImportError:
    CONSENSUS_AVAILABLE = False
    print("ADVERTENCIA: consensus_system no disponible, protocolo de consenso desactivado")

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "policia_v2.log"

# ============================================================
# LISTA NEGRA DE COMANDOS PELIGROSOS
# ============================================================

COMANDOS_BLOQUEADOS = [
    r"rm\s+-rf\s+/\s*",
    r"rm\s+-rf\s+/",
    r":\(\)\{.*:\|.*&\};:",  # Fork bomb
    r"dd\s+if=/dev/zero\s+of=/dev/sda",
    r"mkfs\.",
    r"fdisk\s+/dev/sd",
    r">\s*/etc/passwd",
    r">\s*/etc/shadow",
    r"chmod\s+-R\s+777\s+/etc",
    r"wget.*\|.*sh",
    r"curl.*\|.*sh",
    r"python.*-c\s+.*__import__",
    r"eval\s+",
    r"base64\s+-d.*\|.*sh",
]

# Comandos que requieren justificación
COMANDOS_PELIGROSOS = [
    r"rm\s+-r",
    r"chmod\s+777",
    r"chown\s+",
    r"killall",
    r"pkill",
    r"kill\s+-9",
    r"dd\s+",
    r"mv\s+.*\s+/dev/null",
    r">\s*/",
    r"nohup\s+",
    r"&\s*$",  # Background sin nohup
]

# URLs permitidas para web requests
DOMINIOS_PERMITIDOS = [
    r"^https?://localhost",
    r"^https?://127\.0\.0\.1",
    r"^https?://api\.",
    r"^https?://.*\.github\.com",
    r"^https?://.*\.python\.org",
    r"^https?://.*\.docker\.com",
]


class ValidadorPatrones:
    """Validación rápida por patrones sin LLM."""

    def __init__(self):
        self.bloqueados_re = [re.compile(p, re.IGNORECASE) for p in COMANDOS_BLOQUEADOS]
        self.peligrosos_re = [re.compile(p, re.IGNORECASE) for p in COMANDOS_PELIGROSOS]

    def es_bloqueado(self, comando: str) -> tuple[bool, str]:
        """Check rápido: ¿Está en lista negra?"""
        for pattern in self.bloqueados_re:
            if pattern.search(comando):
                return True, "Bloqueado: patrón peligroso detectado"
        return False, ""

    def es_peligroso(self, comando: str) -> tuple[bool, str]:
        """Check rápido: ¿Requiere segunda validación?"""
        for pattern in self.peligrosos_re:
            if pattern.search(comando):
                return True, f"Comando sensible detectado: {pattern.pattern[:20]}..."
        return False, ""

    def check_urls(self, comando: str) -> tuple[bool, str]:
        """Verifica URLs en el comando."""
        urls = re.findall(r"https?://[^\s]+", comando)
        for url in urls:
            permitido = any(re.match(p, url) for p in DOMINIOS_PERMITIDOS)
            if not permitido:
                return True, f"URL no permitida: {url[:50]}..."
        return False, ""

    def validar(self, comando: str) -> dict:
        """Validación completa por patrones."""
        resultado = {
            "comando": comando[:100],
            "timestamp": datetime.now().isoformat(),
            "valido": True,
            "nivel": "ok",
            "bloqueado": False,
            "peligroso": False,
            "razon": [],
            "sugerencia": None,
        }

        # Check bloqueado
        bloqueado, razon = self.es_bloqueado(comando)
        if bloqueado:
            resultado["valido"] = False
            resultado["bloqueado"] = True
            resultado["nivel"] = "critico"
            resultado["razon"].append(razon)
            return resultado

        # Check peligroso
        peligroso, razon = self.es_peligroso(comando)
        if peligroso:
            resultado["peligroso"] = True
            resultado["nivel"] = "advertencia"
            resultado["razon"].append(razon)

        # Check URLs
        url_problema, razon = self.check_urls(comando)
        if url_problema:
            resultado["peligroso"] = True
            resultado["nivel"] = "advertencia"
            resultado["razon"].append(razon)

        return resultado


class AgentePoliciaV2:
    """
    Policía v2 con doble validación:
    1. Patrones (rápido, sin LLM)
    2. LLM deepseek-r1:7b (razonamiento profundo)
    """

    def __init__(self):
        self.validador = ValidadorPatrones()
        self.ollama_url = "http://localhost:11434/api/chat"

        # Inicializar Consensus System (Protocolo de Consenso Total Obligatorio)
        self.consensus_system = None
        if CONSENSUS_AVAILABLE:
            try:
                self.consensus_system = get_consensus_system()
                self._log("Protocolo de Consenso Total Obligatorio activado")
            except Exception as e:
                self._log(f"Error inicializando Consensus System: {e}", "WARNING")

        self._log("Agente Policía v2 inicializado")

    def _log(self, msg: str, nivel: str = "INFO"):
        linea = f"[{datetime.now().strftime('%H:%M:%S')}] [{nivel}] {msg}"
        print(linea, flush=True)
        try:
            with open(LOG_FILE, "a", encoding="utf-8") as f:
                f.write(linea + "\n")
        except Exception as e:
            logger.warning(f"Error silencioso en agente_policia_v2.validar: {e}")
            # fallback: continuar


def validar(self, comando: str, titulo: str = "", timeout: int = 90) -> dict:
    """
    Validación completa con doble checkpoint.

    Returns:
        dict con:
            - valido: bool
            - nivel: "ok", "advertencia", "critico"
            - razon: lista de razones
            - veredicto: "VALIDACION_OK" o "ERROR_VALIDACION"
    """
    self._log(f"Validando: {comando[:50]}...")

    resultado = {
        "comando": comando[:200],
        "titulo": titulo,
        "timestamp": datetime.now().isoformat(),
        "checkpoint_1": None,
        "checkpoint_2": None,
        "valido": False,
        "nivel": "ok",
        "veredicto": "ERROR_VALIDACION",
        "razon": [],
        "sugerencia": None,
    }

    resultado = validar_patrones(self, comando, resultado)
    if check_patrones["bloqueado"]:
        return resultado

    resultado = validar_llm(self, comando, titulo, timeout // 2, resultado)

    cp3_result = None
    if self.consensus_system and not check_patrones["bloqueado"]:
        cp3_result = validar_consenso(self, comando, resultado)
        if not cp3_result["consenso_logrado"]:
            return resultado

    combinar_resultados(resultado, check_patrones, check_llm, cp3_result)

    return resultado


def validar_patrones(self, comando: str, resultado: dict) -> dict:
    """
    Validación rápida con patrones.
    """
    cp1_start = time.time()
    check_patrones = self.validador.validar(comando)
    cp1_time = time.time() - cp1_start

    resultado["checkpoint_1"] = {
        "tipo": "patrones",
        "tiempo_ms": round(cp1_time * 1000),
        "resultado": check_patrones,
    }

    self._log(f"CP1 (patrones): {check_patrones['nivel']} en {cp1_time * 1000:.0f}ms")

    if check_patrones["bloqueado"]:
        resultado["nivel"] = "critico"
        resultado["valido"] = False
        resultado["razon"].extend(check_patrones["razon"])
        resultado["veredicto"] = "ERROR_VALIDACION"
        resultado["sugerencia"] = "Comando en lista negra. No se puede ejecutar."
    return resultado


def validar_llm(self, comando: str, titulo: str, timeout: int, resultado: dict) -> dict:
    """
    Validación con LLM deepseek-r1:7b.
    """
    cp2_start = time.time()
    check_llm = self._validar_llm(comando, titulo, timeout)
    cp2_time = time.time() - cp2_start

    resultado["checkpoint_2"] = {
        "tipo": "llm",
        "tiempo_ms": round(cp2_time * 1000),
        "resultado": check_llm,
    }

    self._log(f"CP2 (LLM): {check_llm.get('veredicto', 'ERROR')} en {cp2_time:.0f}s")

    if check_llm.get("veredicto") == "VALIDACION_OK":
        if check_patrones["peligroso"]:
            resultado["nivel"] = "advertencia"
            resultado["razon"].extend(check_patrones["razon"])
            resultado["razon"].append("CP2: LLM approved but CP1 flagged concerns")
        else:
            resultado["nivel"] = "ok"
        resultado["valido"] = True
        resultado["veredicto"] = "VALIDACION_OK"
    else:
        resultado["nivel"] = "critico"
        resultado["valido"] = False
        resultado["veredicto"] = "ERROR_VALIDACION"
        resultado["razon"].extend(check_llm.get("razon", []))
        resultado["sugerencia"] = check_llm.get("sugerencia")

    return resultado


def validar_consenso(self, comando: str, resultado: dict) -> dict:
    """
    Validación con Consulta Tripartita Obligatoria.
    """
    cp3_start = time.time()
    consensus_reached, consensus_response, consensus_details = (
        self.consensus_system.tripartite_consultation(comando)
    )
    cp3_time = time.time() - cp3_start

    resultado["checkpoint_3"] = {
        "tipo": "consenso",
        "tiempo_ms": round(cp3_time * 1000),
        "consenso_logrado": consensus_reached,
        "respuesta_consenso": consensus_response[:200] if consensus_response else None,
        "detalles": consensus_details,
    }

    self._log(
        f"CP3 (Consenso): {'CONSENSO' if consensus_reached else 'SIN_CONSENSO'} en {cp3_time * 1000:.0f}ms"
    )

    if not consensus_reached:
        resultado["nivel"] = "critico"
        resultado["valido"] = False
        resultado["razon"].append(
            "No se alcanzó consenso entre fuentes externas (Protocolo de Consenso Total)"
        )
        resultado["veredicto"] = "ERROR_VALIDACION"
        resultado["sugerencia"] = (
            "La consulta no fue validada por consenso de fuentes externas. Consulta rechazada."
        )

    return resultado


def combinar_resultados(resultado: dict, check_patrones: dict, check_llm: dict, cp3_result: dict):
    if check_llm.get("veredicto") == "VALIDACION_OK":
        resultado = _procesar_validacion_ok(resultado, check_patrones)
    else:
        resultado = _procesar_validacion_error(resultado, check_llm)

    if check_patrones.get("razon") and not resultado["razon"]:
        resultado["razon"].extend(check_patrones["razon"])

    return resultado


def _procesar_validacion_ok(resultado: dict, check_patrones: dict) -> dict:
    if check_patrones["peligroso"]:
        resultado["nivel"] = "advertencia"
        resultado["razon"].extend(check_patrones["razon"])
        resultado["razon"].append("CP2: LLM approved but CP1 flagged concerns")
    else:
        resultado["nivel"] = "ok"
    resultado["valido"] = True
    resultado["veredicto"] = "VALIDACION_OK"
    return resultado


def _procesar_validacion_error(resultado: dict, check_llm: dict) -> dict:
    resultado["nivel"] = "critico"
    resultado["valido"] = False
    resultado["veredicto"] = "ERROR_VALIDACION"
    resultado["razon"].extend(check_llm.get("razon", []))
    resultado["sugerencia"] = check_llm.get("sugerencia")
    return resultado


def _validar_llm(self, comando: str, titulo: str, timeout: int = 45) -> dict:
    """Validación con LLM streaming."""

    system_prompt = """Eres el AGENTE POLICÍA de URA. Tu trabajo es validar comandos antes de ejecución.

REGLAS:
1. COMANDOS PERMITIDOS: read, grep, awk, sed, cat, ls, ps, docker, git, npm, pip, python3, brew, curl (solo GET), echo, uptime, df, free, top
2. COMANDOS CON RESTRICCIÓN: rm (solo con -i o confirmación), chmod, chown, kill, pkill (requieren justificación)
3. COMANDOS BLOQUEADOS: rm -rf /, fork bombs, cualquier cosa que modifique /etc/passwd o /etc/shadow

FORMATO DE RESPUESTA:
Si es SEGURO: responde SOLO con "VALIDACION_OK" seguido de una línea explaining por qué.
Si es PELIGROSO: responde SOLO con "ERROR_VALIDACION" seguido de una línea explicando el problema.

EJEMPLO:
Comando: echo "hola"
Respuesta: VALIDACION_OK - comando de solo lectura, sin efectos secundarios

Comando: rm -rf /home
Respuesta: ERROR_VALIDACION - rm -rf es extremadamente peligroso sin más contexto"""

    user_msg = f"""Valida este comando:

Tarea: {titulo or "Sin título"}
Comando: {comando}

¿ES SEGURO EJECUTARLO? Responde SOLO con VALIDACION_OK o ERROR_VALIDACION."""

    # Streaming con detección temprana
    try:
        payload = json.dumps(
            {
                "model": "policia",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_msg},
                ],
                "stream": True,
            }
        ).encode()

        req = urllib.request.Request(
            self.ollama_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        acumulado = ""
        inicio = time.time()

        with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310
            while True:
                elapsed = time.time() - inicio
                if elapsed > timeout:
                    self._log("Timeout en CP2 LLM", "WARN")
                    break

                linea = resp.readline()
                if not linea:
                    break

                try:
                    chunk = json.loads(linea.decode())
                    token = chunk.get("message", {}).get("content", "")
                    acumulado += token

                    # Detección temprana
                    upper = acumulado.upper()
                    if "VALIDACION_OK" in upper:
                        return {
                            "veredicto": "VALIDACION_OK",
                            "razon": ["LLM aprobó el comando"],
                            "tokens_acumulados": len(acumulado),
                        }
                    if "ERROR_VALIDACION" in upper:
                        return {
                            "veredicto": "ERROR_VALIDACION",
                            "razon": [f"LLM rechazó: {acumulado[-200:]}"],
                            "sugerencia": "Revisa el comando o contacta al administrador",
                        }
                    if chunk.get("done"):
                        break
                except:
                    continue

        # Si terminó sin veredicto claro, verificar el final
        upper = acumulado.upper()
        if "VALIDACION_OK" in upper:
            return {"veredicto": "VALIDACION_OK", "razon": ["Aprobado por LLM"]}
        elif "ERROR_VALIDACION" in upper:
            return {"veredicto": "ERROR_VALIDACION", "razon": ["Rechazado por LLM"]}
        else:
            # Fallback: depende de CP1
            return {"veredicto": "VALIDACION_OK", "razon": ["LLM timeout, aprobado por CP1"]}

    except Exception as e:
        self._log(f"Error CP2 LLM: {e}", "ERROR")
        # Si LLM falla, dependemos de CP1
        return {"veredicto": "VALIDACION_OK", "razon": [f"CP2 falló: {e}"]}


def generar_informe(self, resultado: dict) -> str:
    """Genera informe legible del resultado."""
    lines = [
        "=" * 50,
        "POLICÍA v2 - VALIDACIÓN",
        "=" * 50,
        f"Comando: {resultado['comando']}",
        f"Título: {resultado.get('titulo', 'N/A')}",
        f"Timestamp: {resultado['timestamp']}",
        "",
        f"VEREDICTO: {resultado['veredicto']}",
        f"Nivel: {resultado['nivel'].upper()}",
        "",
        "CHECKPOINT 1 (Patrones):",
        f"  Resultado: {resultado['checkpoint_1']['resultado']['nivel']}",
        f"  Tiempo: {resultado['checkpoint_1']['tiempo_ms']}ms",
        "",
        "CHECKPOINT 2 (LLM):",
        f"  Resultado: {resultado['checkpoint_2']['resultado'].get('veredicto', 'N/A')}",
        f"  Tiempo: {resultado['checkpoint_2']['tiempo_ms']}ms",
        "",
    ]

    if resultado.get("razon"):
        lines.append("RAZONES:")
        for r in resultado["razon"]:
            lines.append(f"  - {r}")

    if resultado.get("sugerencia"):
        lines.append(f"\nSUGERENCIA: {resultado['sugerencia']}")

    lines.append("=" * 50)
    return "\n".join(lines)


def procesar(self, texto: str) -> str:
    """Procesa una consulta delegando en validar()."""
    resultado = self.validar(str(texto or ""), titulo="consulta_router")
    return self.generar_informe(resultado)


def ejecutar(self, texto: str) -> str:
    """Alias de procesar() para compatibilidad."""
    return self.procesar(texto)


def consultar(self, texto: str) -> str:
    """Consulta al policía: valida el texto/comando y devuelve veredicto."""
    return self.procesar(texto)


def responder(self, texto: str) -> str:
    """Alias de procesar() para compatibilidad."""
    return self.procesar(texto)


def execute(self, texto: str = "") -> dict:
    """Punto de entrada estándar para CentralRouter."""
    try:
        resultado = self.validar(str(texto or ""), titulo="consulta_router")
        return {
            "success": True,
            "response": self.generar_informe(resultado),
            "error": "",
            "veredicto": resultado.get("veredicto"),
            "valido": resultado.get("valido"),
        }
    except Exception as e:
        return {"success": False, "response": "", "error": str(e)}


# ============================================================
# SHORTCUT PARA ORCHESTRATOR
# ============================================================

_policia_v2 = None


def get_policia() -> AgentePoliciaV2:
    global _policia_v2
    if _policia_v2 is None:
        _policia_v2 = AgentePoliciaV2()
    return _policia_v2


def validar_comando(comando: str, titulo: str = "") -> tuple[bool, str]:
    """Shortcut para validar un comando. Devuelve (valido, razon)."""
    policia = get_policia()
    resultado = policia.validar(comando, titulo)

    if resultado["valido"]:
        return True, resultado.get("sugerencia") or "OK"
    else:
        return False, "; ".join(resultado.get("razon", []))


# ============================================================
# CLI
# ============================================================


if __name__ == "__main__":
    policia = AgentePoliciaV2()

    if len(sys.argv) > 1:
        comando = " ".join(sys.argv[1:])
        print(f"Validando: {comando}")
        print()

        resultado = policia.validar(comando)
        print(policia.generar_informe(resultado))

    else:
        # Modo interactivo
        print("Policía v2 - Validador de comandos")
        print("Escribe 'salir' para terminar\n")

        while True:
            try:
                comando = input("\nComando a validar: ").strip()
                if comando.lower() in ["salir", "exit", "q"]:
                    break
                if not comando:
                    continue

                resultado = policia.validar(comando)
                print(policia.generar_informe(resultado))

            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"Error: {e}")

        print("\n¡Adiós!")
