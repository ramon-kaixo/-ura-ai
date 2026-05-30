#!/usr/bin/env python3
"""
URA - Command Detectors
Funciones para detectar tipos de comandos en mensajes del usuario
"""

import re


def is_screen_area_command(message: str) -> bool:
    """Detectar comandos de selección de área"""
    triggers = [
        r"\bexplica\s+esta\s+área",
        r"\bqué\s+es\s+esto",
        r"\banaliza\s+esta\s+parte",
        r"\bselecciona\s+área",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))


def is_windsurf_command(message: str) -> bool:
    """Detectar comandos de Windsurf"""
    triggers = [
        r"\babre\s+Windsurf",
        r"\bdile\s+a\s+Windsurf\s+que\s+",
        r"\bejecuta\s+el\s+código\s+que\s+generó\s+Windsurf",
        r"\bdime\s+cómo\s+se\s+hace\s+\w+\s+en\s+Windsurf",
        r"\bnecesito\s+un\s+script\s+que\s+",
        r"\bgenera\s+un\s+script\s+que\s+",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))


def is_app_command(message: str) -> bool:
    """Detectar comandos de aplicaciones"""
    triggers = [
        r"\babre\s+(\w+)",
        r"\bdame\s+permiso\s+para\s+(\w+)",
        r"\bbusca\s+en\s+(\w+)",
        r"\bcopia\s+de\s+(\w+)\s+a\s+(\w+)",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))


def is_manual_command(message: str) -> bool:
    """Detectar comandos de consulta de manuales"""
    triggers = [
        r"\bcómo\s+se\s+usa\s+(\w+)",
        r"\bmanual\s+de\s+(\w+)",
        r"\bguíame\s+para\s+usar\s+(\w+)",
        r"\benseñame\s+a\s+usar\s+(\w+)",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))


def is_install_command(message: str) -> bool:
    """Detectar comandos de instalación"""
    triggers = [
        r"\binstala\s+",
        r"\binstall\s+",
        r"\binstalar\s+",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))


def is_visual_automation_command(message: str) -> bool:
    """Detectar comandos de automatización visual"""
    triggers = [
        r"\bgu[ií]ame\s+(para|a)\s+",
        r"\bay[uú]dame\s+a\s+",
        r"\bautomatiza\s+",
        r"\bconfigura\s+",
    ]
    pattern = re.compile("|".join(triggers), flags=re.IGNORECASE)
    return bool(pattern.search(message))
