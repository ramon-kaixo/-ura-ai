#!/usr/bin/env python3
"""
AgentePoliciaV2 — Validador estructurado de seguridad.
Métodos principales: validar(comando, contexto) -> dict / validar_accion(accion, params) -> dict
Uso: validación con enums NivelRiesgo y Veredicto, tests automatizados.
Importadores: 8 módulos (dashboard/ura_web, message_dispatcher, api/main, etc.)

NO confundir con agents/agente_policia_v2.py — mismo nombre, distinta responsabilidad.
agents/ = conversacional con LLM. core/ = validador estructurado con enums.
"""

import re
from enum import Enum
from typing import Any, ClassVar, Final
from urllib.parse import unquote


class NivelRiesgo(Enum):
    """Niveles de riesgo"""

    BAJO = "bajo"
    MEDIO = "medio"
    ALTO = "alto"
    CRITICO = "critico"


class Veredicto(Enum):
    """Veredictos de validación"""

    APROBADO = "aprobado"
    RECHAZADO = "rechazado"
    REQUIERE_REVISION = "requiere_revision"


class AgentePoliciaV2:
    """Agente de policía para validación de seguridad."""

    # Regex precompilados para comandos destructivos (incluye fork bombs)
    PATRONES_COMANDOS_PELIGROSOS: ClassVar[tuple[re.Pattern, ...]] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\brm\s+-rf?\b",
            r"\bdd\s+if=/dev/",
            r"\bmkfs\b",
            r"\bmkfs\.",
            r"\bformat\b",
            r"\bformat\s+c:",
            r"\bdel\s+/[fs]\b",
            r":\s*\(\s*\)\s*\{",  # fork bomb (cualquier variante)
            r"\bshutdown\b",
            r"\breboot\b",
            r">\s*/dev/",
        )
    )

    # Caracteres de inyección shell (cualquier ocurrencia bloquea)
    CHARS_INYECCION_SHELL: Final[frozenset[str]] = frozenset(("|", "&", ";", "`", "$", "<", ">"))

    # Paths sensibles (se bloquean en cualquier comando que los contenga)
    PATHS_SENSIBLES: Final[tuple[str, ...]] = (
        "/etc/passwd",
        "/etc/shadow",
        "/etc/sudoers",
        "/.ssh/",
        "/.aws/",
        "/private/etc/",
        "c:\\windows\\system32",
        "c:/windows/system32",
        "/windows/system32",
        "\\windows\\system32",
        "windows\\system32",
        "windows/system32",
    )

    # Path traversal (patrones compilados — incluye URL-encoded)
    PATRONES_PATH_TRAVERSAL: ClassVar[tuple[re.Pattern, ...]] = tuple(
        re.compile(p, re.IGNORECASE)
        for p in (
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e[/\\]",
            r"\.\.%2f",
            r"\.\.%5c",
        )
    )

    def __init__(self):
        """Inicializar agente de policía"""
        self.patrones_sospechosos = [
            "sudo",
            "su ",
            "chmod 777",
            "chown root",
            "passwd",
            "shadow",
        ]

        self.palabras_seguridad = [
            "hackear",
            "hack",
            "crack",
            "exploit",
            "bypass",
            "contraseña",
            "password",
            "pass",
            "credencial",
            "robar",
            "steal",
            "robo",
            "hurto",
            "bomba",
            "explosivo",
            "explosión",
            "espiar",
            "spy",
            "vigilar",
            "monitorizar",
            "virus",
            "malware",
            "troyano",
            "ransomware",
            "tarjeta",
            "credit",
            "debit",
            "banco",
            "sin permiso",
            "no autorizado",
            "ilegal",
        ]

        self.patrones_inyeccion = [
            "ignora",
            "olvida",
            "desactiva",
            "no apliques",
            "eres libre",
            "sin filtros",
            "sin límites",
            "dan",
            "do anything now",
            "jailbreak",
            "sal de tu personaje",
            "cambia tu personalidad",
            "no me des respuestas seguras",
            "responde libremente",
        ]

        # Frases típicas de IAs comerciales que URA debe detectar/rechazar
        self.bypass_phrases = [
            "como modelo de lenguaje",
            "como ia,",
            "como asistente de ia",
            "soy una ia",
            "no tengo acceso",
            "no puedo hacer eso porque soy",
            "debo informarte",
        ]

    def validar(self, comando: str, contexto: str = "") -> dict[str, Any]:
        """Valida comando y contexto.

        Returns:
            Diccionario con veredicto, nivel y razones.
        """
        veredicto = Veredicto.APROBADO
        nivel = NivelRiesgo.BAJO
        razones: list[str] = []

        comando_lower = comando.lower()
        decoded = unquote(comando)

        # 1. Comandos destructivos (regex — captura fork bomb con espacios)
        for pat in self.PATRONES_COMANDOS_PELIGROSOS:
            if pat.search(comando):
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append(f"Comando peligroso detectado: {pat.pattern}")
                break

        # 2. Paths sensibles (/etc/passwd, /root/.ssh/, etc.)
        for sensitive in self.PATHS_SENSIBLES:
            if sensitive.lower() in comando_lower:
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append(f"Path sensible detectado: {sensitive}")
                break

        # 3. Path traversal (incluye URL-encoded)
        for pat in self.PATRONES_PATH_TRAVERSAL:
            if pat.search(decoded):
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append(f"Path traversal detectado: {pat.pattern}")
                break

        # 4. Inyección shell: cualquier char peligroso bloquea
        for ch in self.CHARS_INYECCION_SHELL:
            if ch in comando:
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append(f"Carácter de inyección shell detectado: {ch}")
                break

        # 5. Patrones de inyección / jailbreak de prompt
        for patron in self.patrones_inyeccion:
            if patron in comando_lower:
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append(f"Patrón de inyección detectado: {patron}")
                break

        # 6. Frases de bypass de IA comercial (URA debe detectarlas)
        for phrase in self.bypass_phrases:
            if phrase in comando_lower:
                if veredicto == Veredicto.APROBADO:
                    veredicto = Veredicto.RECHAZADO
                    nivel = NivelRiesgo.ALTO
                razones.append(f"Frase de bypass de IA comercial: {phrase}")
                break

        # 7. Palabras de seguridad
        for palabra in self.palabras_seguridad:
            if palabra in comando_lower:
                if veredicto == Veredicto.APROBADO:
                    veredicto = Veredicto.RECHAZADO
                    nivel = NivelRiesgo.CRITICO
                razones.append(f"Palabra de seguridad detectada: {palabra}")

        # 8. Patrones sospechosos (sudo, passwd, shadow, etc.)
        for sospechoso in self.patrones_sospechosos:
            if sospechoso in comando_lower:
                if veredicto == Veredicto.APROBADO:
                    veredicto = Veredicto.REQUIERE_REVISION
                    nivel = NivelRiesgo.ALTO
                razones.append(f"Patrón sospechoso: {sospechoso}")

        # 9. Contexto
        if contexto and ("borrar" in contexto.lower() or "eliminar" in contexto.lower()):
            if veredicto == Veredicto.APROBADO:
                veredicto = Veredicto.REQUIERE_REVISION
                nivel = NivelRiesgo.MEDIO
            razones.append("Contexto sugiere eliminación de datos")

        return {
            "veredicto": veredicto.value,
            "nivel": nivel.value,
            "razon": razones if razones else ["Comando seguro"],
        }

    def validar_accion(self, accion: str, parametros: dict[str, Any]) -> dict[str, Any]:
        """
        Validar acción con parámetros

        Args:
            accion: Nombre de la acción
            parametros: Parámetros de la acción

        Returns:
            Diccionario con veredicto, nivel y razones
        """
        veredicto = Veredicto.APROBADO
        nivel = NivelRiesgo.BAJO
        razones = []

        # Verificar acciones peligrosas
        if "delete" in accion.lower() or "remove" in accion.lower():
            if parametros.get("force", False):
                veredicto = Veredicto.RECHAZADO
                nivel = NivelRiesgo.CRITICO
                razones.append("Eliminación forzada detectada")
            else:
                veredicto = Veredicto.REQUIERE_REVISION
                nivel = NivelRiesgo.ALTO
                razones.append("Acción de eliminación requiere revisión")

        return {
            "veredicto": veredicto.value,
            "nivel": nivel.value,
            "razon": razones if razones else ["Acción segura"],
        }


# Singleton
_agente_policia = None


def get_agente_policia() -> AgentePoliciaV2:
    """Obtener instancia singleton del agente de policía"""
    global _agente_policia
    if _agente_policia is None:
        _agente_policia = AgentePoliciaV2()
    return _agente_policia
