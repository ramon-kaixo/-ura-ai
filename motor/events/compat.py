from __future__ import annotations

import logging

log = logging.getLogger("ura.compat")


def check_api_compatibility(
    plugin_api_version: str,
    motor_api_version: str,
    *,
    allow_legacy: bool = True,
) -> bool:
    if not plugin_api_version:
        if allow_legacy:
            log.warning("Plugin sin api_version — compatibilidad legacy F9/F10")
            return True
        return False

    try:
        p_major, p_minor, *_ = (int(x) for x in plugin_api_version.split("."))
        m_major, m_minor, *_ = (int(x) for x in motor_api_version.split("."))
    except (ValueError, AttributeError):
        log.warning("api_version inválida: plugin=%s motor=%s", plugin_api_version, motor_api_version)
        return False

    if p_major != m_major:
        log.warning(
            "Incompatible: plugin API v%s, motor API v%s (MAJOR mismatch)",
            plugin_api_version,
            motor_api_version,
        )
        return False

    if p_minor > m_minor:
        log.warning(
            "Incompatible: plugin API v%s, motor API v%s (plugin requiere MINOR más reciente)",
            plugin_api_version,
            motor_api_version,
        )
        return False

    return True


def check_plugin_dependency(  # noqa: PLR0911
    dep_name: str,
    dep_version_spec: str,
    installed_version: str,
) -> bool:
    if not dep_version_spec or dep_version_spec == "*":
        return True

    if ">=" in dep_version_spec and "<" in dep_version_spec:
        parts = dep_version_spec.split("<")
        lower = parts[0].replace(">=", "").strip()
        upper = parts[1].strip() if len(parts) > 1 else ""
        return _semver_gte(installed_version, lower) and (not upper or _semver_lt(installed_version, upper))

    if dep_version_spec.startswith(">="):
        min_v = dep_version_spec[2:].strip()
        return _semver_gte(installed_version, min_v)
    if dep_version_spec.startswith("=="):
        exact = dep_version_spec[2:].strip()
        return installed_version == exact
    if dep_version_spec.startswith("<"):
        max_v = dep_version_spec[1:].strip()
        return _semver_lt(installed_version, max_v)
    if dep_version_spec.startswith("~="):
        compat = dep_version_spec[2:].strip()
        return _semver_compatible(installed_version, compat)
    return True  # unknown spec — accept


def _parse_ver(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def _semver_gte(installed: str, minimum: str) -> bool:
    return _parse_ver(installed) >= _parse_ver(minimum)


def _semver_lt(installed: str, maximum: str) -> bool:
    return _parse_ver(installed) < _parse_ver(maximum)


def _semver_compatible(installed: str, compat: str) -> bool:
    i = _parse_ver(installed)
    c = _parse_ver(compat)
    if len(c) >= 2:
        return i[0] == c[0] and i[1] >= c[1]
    return i[0] == c[0]
