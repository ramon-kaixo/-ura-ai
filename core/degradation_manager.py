#!/usr/bin/env python3
"""
Gestor de degradación inteligente para URA
Encapsula la lógica de degradación cuando un agente falla
"""


class DegradationManager:
    """Gestor de degradación inteligente."""

    def __init__(self, intent_keywords: dict[str, list[str]] = None):
        self.intent_keywords = intent_keywords or {}
        self.category_map = self._build_category_map()


def _build_category_map(self) -> dict[str, str]:
    return {
        **_map_cocina(),
        **_map_contabilidad(),
        **_map_marketing(),
        **_map_legal(),
        **_map_rrhh(),
        **_map_sistema(),
        **_map_documentos(),
        **_map_comunicacion(),
        **_map_ia(),
        **_map_supervision(),
        **_map_especiales(),
        **_map_orquestacion(),
    }


def _map_cocina() -> dict[str, str]:
    return {
        "cocina_espanola": "cocina",
        "cocina_navarra": "cocina",
        "cocina_italiana": "cocina",
        "cocina_mexicana": "cocina",
        "cocina_peruana": "cocina",
        "gastronomo_musica": "cocina",
        "orquestador_recetas": "cocina",
        "media_recetas": "cocina",
        "vocabulario_gastronomico": "cocina",
        "vocabulario_bar": "cocina",
        "cocina_internacional": "cocina",
        "recetas_con_media": "cocina",
    }


def _map_contabilidad() -> dict[str, str]:
    return {
        "administrativo_contable": "contabilidad",
        "contabilidad": "contabilidad",
        "facturas": "contabilidad",
        "banco": "contabilidad",
        "vocabulario_financiero": "contabilidad",
        "contabilidad_agent": "contabilidad",
    }


def _map_marketing() -> dict[str, str]:
    return {
        "marketing": "marketing",
        "creativo_marketing": "marketing",
        "marketing_navarra": "marketing",
        "galeria_videos": "marketing",
        "galeria_fotos": "marketing",
        "lenguaje_creativo": "marketing",
        "marketing_agent": "marketing",
        "tendencias_pamplona": "marketing",
    }


def _map_legal() -> dict[str, str]:
    return {
        "juridico": "legal",
        "policia": "legal",
        "vocabulario_legal": "legal",
        "leyes_agent": "legal",
    }


def _map_rrhh() -> dict[str, str]:
    return {
        "rrhh": "rrhh",
        "laboral": "rrhh",
        "rrhh_camaras": "rrhh",
    }


def _map_sistema() -> dict[str, str]:
    return {
        "tailscale": "sistema",
        "automatizador": "sistema",
        "automatizacion": "sistema",
        "conectividad": "sistema",
        "red_telefonia": "sistema",
        "hardware": "sistema",
        "scheduler": "sistema",
        "gobierno": "sistema",
        "sistemas": "sistema",
        "red": "sistema",
        "backup": "sistema",
        "seguridad": "sistema",
        "rendimiento": "sistema",
        "instalador": "sistema",
        "camaras": "sistema",
        "arquitectura": "sistema",
        "clasificador": "sistema",
        "registry": "sistema",
        "gui": "sistema",
    }


def _map_documentos() -> dict[str, str]:
    return {
        "documentos_pdf": "documentos",
        "documentos_texto": "documentos",
        "documentos_word": "documentos",
        "documentos_excel": "documentos",
        "documentos_presentaciones": "documentos",
        "orquestador_documentacion": "documentos",
        "archivist": "documentos",
        "librarian": "documentos",
        "biblioteca": "documentos",
        "bibliotecario_pasillo": "documentos",
    }


def _map_comunicacion() -> dict[str, str]:
    return {
        "email": "comunicacion",
        "notificaciones": "comunicacion",
        "conversacion": "comunicacion",
        "telegram_dam": "comunicacion",
        "notificador_dam": "comunicacion",
    }


def _map_ia() -> dict[str, str]:
    return {
        "investigador_ia": "ia",
        "conciencia": "ia",
        "memoria": "ia",
        "lenguaje": "ia",
        "vocabulario": "ia",
        "vocabulario_codigo": "ia",
        "vocabulario_tecnico": "ia",
        "vocabulario_bar": "ia",
        "modelos": "ia",
        "lenguaje_escribiente": "ia",
        "lenguaje_tecnico": "ia",
        "vision": "ia",
        "opencode": "ia",
    }


def _map_supervision() -> dict[str, str]:
    return {
        "verificador": "supervision",
        "auditor": "supervision",
        "auditor_externo": "supervision",
        "supervisor": "supervision",
        "revisor": "supervision",
        "reparador": "supervision",
        "guardian_residente": "supervision",
    }


def _map_especiales() -> dict[str, str]:
    return {
        "motor_autorizacion_dual": "especiales",
        "doble_verificacion": "especiales",
        "servidor_validacion": "especiales",
        "asesor": "especiales",
    }


def _map_orquestacion() -> dict[str, str]:
    return {
        "busqueda": "orquestacion",
        "orquestador_documentacion": "orquestacion",
    }

    def find_similar_agent(self, failed_intent: str) -> str | None:
        """
        Encontrar agente similar basándose en categorías.

        Args:
            failed_intent: Intención que falló

        Returns:
            Intención similar o None
        """
        failed_keywords = set(self.intent_keywords.get(failed_intent, []))
        failed_category = self.category_map.get(failed_intent)

        if not failed_category:
            return None

        candidates = []

        for intent, keywords in self.intent_keywords.items():
            if intent == failed_intent:
                continue

            current_category = self.category_map.get(intent)
            if current_category == failed_category:
                current_keywords = set(keywords)
                similarity = len(failed_keywords & current_keywords)
                candidates.append((intent, similarity))

        if candidates:
            candidates.sort(key=lambda x: x[1], reverse=True)
            return candidates[0][0]

        return None

    def set_keywords(self, intent_keywords: dict[str, list[str]]) -> None:
        """Establecer keywords por intención."""
        self.intent_keywords = intent_keywords
