#!/usr/bin/env python3
"""
AGENTE COCINA NAVARRA TEMPORADA - Cocina navarra con Soberanía del Producto de Temporada
Implementa la regla de oro: 80% de ingredientes deben ser de temporada actual en Navarra
Incluye calendario estacional, filtro de selección y marketing estacional
"""

import json
import logging
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

# Configuración de logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)


@dataclass
class IngredientesTemporada:
    """Clase para gestionar ingredientes de temporada"""

    nombre: str
    es_temporada: bool
    mes_actual: str
    origen: str
    precio_medio: float
    sustituto: str | None = None
    coste_extra: float = 0.0
    marketing_tag: str | None = None


class AgenteCocinaNavarraTemporada:
    """Agente de cocina navarra con soberanía del producto de temporada"""

    def __init__(self):
        self.logger = logging.getLogger("Agente_Cocina_Navarra_Temporada")

        # Rutas de archivos
        self.base_path = Path(__file__).parent.parent
        self.calendario_path = self.base_path / "data" / "calendario_navarra.json"
        self.db_path = self.base_path / "board.db"

        # Cargar calendario estacional
        self.calendario = self._cargar_calendario()

        # Mes actual
        self.mes_actual = datetime.now().strftime("%B").lower()
        self.mes_espanol = self._obtener_mes_espanol()

        # Configuración de soberanía
        self.config_soberania = self.calendario.get("reglas_soberania", {})
        self.porcentaje_minimo_temporada = self.config_soberania.get(
            "porcentaje_minimo_temporada", 0.8
        )
        self.prioridad_producto_local = self.config_soberania.get("prioridad_producto_local", 0.9)

        # Frases marketing estacional
        self.frases_marketing = self.config_soberania.get("frases_marketing", [])

        self.logger.info(
            f"Agente Cocina Navarra Temporada inicializado - Mes actual: {self.mes_espanol}"
        )

    def _cargar_calendario(self) -> dict[str, Any]:
        """Cargar calendario estacional de Navarra"""
        try:
            with open(self.calendario_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Calendario no encontrado en {self.calendario_path}")
            return {"productos_estrella": {}, "sustitutos_temporada": {}}

    def _obtener_mes_espanol(self) -> str:
        """Obtener nombre del mes en español"""
        meses = {
            "january": "enero",
            "february": "febrero",
            "march": "marzo",
            "april": "abril",
            "may": "mayo",
            "june": "junio",
            "july": "julio",
            "august": "agosto",
            "september": "septiembre",
            "october": "octubre",
            "november": "noviembre",
            "december": "diciembre",
        }
        return meses.get(self.mes_actual, "abril")  # Default a abril si hay error

    def verificar_temporada_ingrediente(self, ingrediente: str) -> IngredientesTemporada:
        """Verifica si un ingrediente es de temporada actual"""
        # Mapeo mejorado de ingredientes a productos del calendario
        mapeo_ingredientes = {
            "espárrago": "espárrago verde",
            "esparrago": "espárrago verde",
            "guisante": "guisante",
            "lechuga": "lechuga",
            "fresa": "fresa",
            "tomate": "tomate",
            "pimiento": "pimiento verde",
            "alcachofa": "alcachofa",
            "cordero": "cordero navarro",
            "ternera": "ternera navarra",
            "queso": "queso de idiazábal",
            "jamón": "jamón de navarra",
            "chistorra": "chistorra navarra",
            "borraja": "borraja",
            "acelga": "acelga",
            "espinaca": "espinaca",
            "cardo": "cardo",
            "boletus": "boletus",
            "níscalo": "níscalo",
            "seta": "seta de cardo",
        }

        # Normalizar ingrediente
        ingrediente_normalizado = mapeo_ingredientes.get(ingrediente.lower(), ingrediente.lower())

        # Buscar en productos estrella del mes actual
        productos_estrella = self.calendario.get("calendario_estacional_navarra", {}).get(
            "productos_estrella", {}
        )
        productos_mes = productos_estrella.get(self.mes_espanol, {})

        # Buscar en todas las categorías del mes actual
        for _categoria, productos in productos_mes.items():
            for producto in productos:
                nombre_producto = producto["nombre"].lower()
                if (
                    nombre_producto in ingrediente_normalizado
                    or ingrediente_normalizado in nombre_producto
                    or any(key in ingrediente_normalizado for key in nombre_producto.split())
                    or any(key in nombre_producto for key in ingrediente_normalizado.split())
                ):
                    return IngredientesTemporada(
                        nombre=producto["nombre"],
                        es_temporada=True,
                        mes_actual=self.mes_espanol,
                        origen=producto.get("origen", "Navarra"),
                        precio_medio=producto.get("precio_medio", 0.0),
                        marketing_tag=(
                            random.choice(self.frases_marketing)
                            if self.frases_marketing
                            else "Producto de Navarra"
                        ),
                    )

        # Buscar en productos permanentes
        productos_permanentes = self.calendario.get("calendario_estacional_navarra", {}).get(
            "productos_permanentes", {}
        )
        for _categoria, productos in productos_permanentes.items():
            for producto in productos:
                nombre_producto = producto["nombre"].lower()
                if (
                    nombre_producto in ingrediente_normalizado
                    or ingrediente_normalizado in nombre_producto
                    or any(key in ingrediente_normalizado for key in nombre_producto.split())
                ):
                    return IngredientesTemporada(
                        nombre=producto["nombre"],
                        es_temporada=True,
                        mes_actual=self.mes_espanol,
                        origen=producto.get("origen", "Navarra"),
                        precio_medio=producto.get("precio_medio", 0.0),
                        marketing_tag=(
                            random.choice(self.frases_marketing)
                            if self.frases_marketing
                            else "Producto de Navarra"
                        ),
                    )

        # No es de temporada, buscar sustituto
        sustitutos = self._buscar_sustituto(ingrediente)
        return IngredientesTemporada(
            nombre=ingrediente,
            es_temporada=False,
            mes_actual=self.mes_espanol,
            origen="Importado",
            precio_medio=0.0,
            sustituto=sustitutos.get("nombre") if sustitutos else None,
            coste_extra=sustitutos.get("coste_extra", 0.5) if sustitutos else 0.5,
            marketing_tag=None,
        )

    def _buscar_sustituto(self, ingrediente: str) -> dict[str, Any] | None:
        """Buscar sustituto para ingrediente fuera de temporada"""
        sustitutos_temporada = self.calendario.get("sustitutos_temporada", {})

        for ingrediente_key, sustituto_info in sustitutos_temporada.items():
            if ingrediente_key in ingrediente.lower():
                if self.mes_espanol in sustituto_info.get("fuera_temporada", []):
                    # Devolver el primer sustituto disponible
                    return sustituto_info["sustitutos"][0]

        return None

    def analizar_receta_temporada(self, receta: dict[str, Any]) -> dict[str, Any]:
        """Analiza una receta y calcula el porcentaje de ingredientes de temporada"""
        ingredientes = receta.get("ingredientes", [])

        ingredientes_analizados = []
        temporada_count = 0
        total_count = len(ingredientes)
        coste_extra_total = 0.0
        marketing_tags = []

        for ingrediente in ingredientes:
            analisis = self.verificar_temporada_ingrediente(ingrediente)
            ingredientes_analizados.append(analisis)

            if analisis.es_temporada:
                temporada_count += 1
                if analisis.marketing_tag:
                    marketing_tags.append(analisis.marketing_tag)
            else:
                coste_extra_total += analisis.coste_extra

        porcentaje_temporada = (temporada_count / total_count) * 100 if total_count > 0 else 0

        return {
            "nombre_receta": receta.get("nombre", "Sin nombre"),
            "ingredientes_analizados": ingredientes_analizados,
            "porcentaje_temporada": porcentaje_temporada,
            "cumple_soberania": porcentaje_temporada >= (self.porcentaje_minimo_temporada * 100),
            "coste_extra_total": coste_extra_total,
            "marketing_tags": list(set(marketing_tags)),  # Eliminar duplicados
            "alertas": self._generar_alertas(porcentaje_temporada, coste_extra_total),
        }

    def _generar_alertas(self, porcentaje_temporada: float, coste_extra: float) -> list[str]:
        """Genera alertas basadas en el análisis de temporada"""
        alertas = []

        if porcentaje_temporada < (self.porcentaje_minimo_temporada * 100):
            alertas.append(
                f"ALERTA: Solo {porcentaje_temporada:.1f}% de ingredientes son de temporada (mínimo requerido: {self.porcentaje_minimo_temporada * 100}%)"
            )

        if coste_extra > self.config_soberania.get("alerta_coste_extra", 0.3):
            alertas.append(
                f"ALERTA: Coste extra por sustitutos: {coste_extra:.2f} (umbral: {self.config_soberania.get('alerta_coste_extra', 0.3)})"
            )

        return alertas

    def generar_menu_temporada(self, precio_menu: float, tipo_menu: str) -> dict[str, Any]:
        """Genera menú basado en productos de temporada"""

        if tipo_menu == "dia":
            return self._generar_menu_dia(precio_menu)
        elif tipo_menu == "fin_semana":
            return self._generar_menu_fin_semana(precio_menu)
        else:
            raise ValueError("Tipo de menú no válido. Use 'dia' o 'fin_semana'")


def _generar_menu_dia(self, precio_menu: float) -> dict[str, Any]:
    """Genera MENÚ DEL DÍA (17) con productos de temporada"""

    menu = self._inicializar_menu(precio_menu)
    primeros = self._generar_primeros()
    segundos = self._generar_segundos()
    postres = self._generar_postres()

    menu["estructura"]["primeros"] = primeros
    menu["estructura"]["segundos"] = segundos
    menu["estructura"]["postres"] = postres

    todos_platos = primeros + segundos + postres
    analisis_global = self._analizar_menu_global(todos_platos)

    menu["analisis_temporada"] = analisis_global
    menu["marketing_tags"] = analisis_global["marketing_tags"]
    menu["porcentaje_temporada_global"] = analisis_global["porcentaje_temporada_promedio"]

    return menu


def _inicializar_menu(self, precio_menu: float) -> dict[str, Any]:
    """Inicializa el menú del día con los datos iniciales"""
    return {
        "nombre": "MENÚ DEL DÍA - SOBERANÍA NAVARRA",
        "precio": precio_menu,
        "tipo": "dia",
        "mes_actual": self.mes_espanol,
        "estructura": {"primeros": [], "segundos": [], "postres": []},
        "marketing_tags": [],
        "porcentaje_temporada_global": 0,
    }


def _generar_primeros(self) -> list[dict[str, Any]]:
    """Genera los primeros platos del menú"""
    return [
        {
            "nombre": "Menestra de verduras de la Ribera con velouté de jamón ibérico",
            "descripcion": "Verduras frescas de temporada con crema suave de jamón",
            "ingredientes": ["espárrago verde", "guisante", "lechuga", "jamón ibérico", "nata"],
            "precio": 8.50,
            "tiempo": "25 min",
            "tendencia": "moderno",
        },
        {
            "nombre": "Ensalada de temporada con queso de Idiazábal",
            "descripcion": "Verduras frescas de Navarra con queso local",
            "ingredientes": ["lechuga", "fresa", "queso idiazábal", "nueces", "vinagreta"],
            "precio": 7.50,
            "tiempo": "15 min",
            "tendencia": "saludable",
        },
        {
            "nombre": "Revuelto de espárragos navarros",
            "descripcion": "Espárragos frescos de la Ribera en revuelto cremoso",
            "ingredientes": ["espárrago verde", "huevo", "ajo", "aceite", "perejil"],
            "precio": 8.00,
            "tiempo": "20 min",
            "tendencia": "tradicional",
        },
        {
            "nombre": "Gazpacho de fresas navarras",
            "descripcion": "Gazpacho dulce con fresas de temporada",
            "ingredientes": ["fresa", "tomate", "pimiento", "cebolla", "pan"],
            "precio": 7.00,
            "tiempo": "10 min",
            "tendencia": "innovador",
        },
    ]


def _generar_segundos(self) -> list[dict[str, Any]]:
    """Genera los segundos platos del menú"""
    return [
        {
            "nombre": "Estofado de rabo de toro deshuesado con parmentier de patata trufada",
            "descripcion": "Rabo navarro cocido a baja temperatura con puré de patata",
            "ingredientes": ["rabo de toro", "patata", "trufa", "vino tinto", "zanahoria"],
            "precio": 12.50,
            "tiempo": "45 min",
            "tendencia": "baja temperatura",
        },
        {
            "nombre": "Lomo de cerdo navarro con guarnición de temporada",
            "descripcion": "Lomo local con verduras frescas de la huerta",
            "ingredientes": ["lomo cerdo", "espárrago", "guisante", "pimiento", "aceite"],
            "precio": 11.00,
            "tiempo": "30 min",
            "tendencia": "moderno",
        },
        {
            "nombre": "Merluza a la plancha con pimientos de Navarra",
            "descripcion": "Pescado fresco con pimientos locales",
            "ingredientes": ["merluza", "pimiento verde", "ajo", "perejil", "limón"],
            "precio": 10.50,
            "tiempo": "20 min",
            "tendencia": "clásico",
        },
        {
            "nombre": "Pollo al chilindrón navarro",
            "descripcion": "Pollo local con salsa de pimientos y cebollas",
            "ingredientes": ["pollo", "pimiento verde", "cebolla", "tomate", "ajo"],
            "precio": 9.50,
            "tiempo": "35 min",
            "tendencia": "tradicional",
        },
    ]


def _generar_postres(self) -> list[dict[str, Any]]:
    """Genera los postres del menú"""
    return [
        {
            "nombre": "Tarta de fresas de Navarra",
            "descripcion": "Tarta casera con fresas frescas de temporada",
            "ingredientes": ["fresa", "nata", "azúcar", "harina", "mantequilla"],
            "precio": 4.50,
            "tiempo": "30 min",
            "tendencia": "casero",
        },
        {
            "nombre": "Flan de huevo con caramelo",
            "descripcion": "Flan tradicional navarro",
            "ingredientes": ["huevo", "leche", "azúcar", "caramelo"],
            "precio": 4.00,
            "tiempo": "45 min",
            "tendencia": "clásico",
        },
        {
            "nombre": "Mousse de yogur con miel de Navarra",
            "descripcion": "Mousse ligero con miel local",
            "ingredientes": ["yogur", "miel", "nata", "gelatina"],
            "precio": 4.00,
            "tiempo": "20 min",
            "tendencia": "saludable",
        },
    ]


def _generar_menu_fin_semana(self, precio_menu: float) -> dict[str, Any]:
    """Genera MENÚ FIN DE SEMANA (22) con productos de temporada"""

    menu = {
        "nombre": "MENÚ FIN DE SEMANA - EXPERIENCIA GASTRONÓMICA NAVARRA",
        "precio": precio_menu,
        "tipo": "fin_semana",
        "mes_actual": self.mes_espanol,
        "estructura": {"platos_centro": [], "segundos": [], "postres": []},
        "marketing_tags": [],
        "porcentaje_temporada_global": 0,
    }

    platos_centro = _generar_platos_centro()
    segundos = _generar_segundos()
    postres = _generar_postres()

    menu["estructura"]["platos_centro"] = platos_centro
    menu["estructura"]["segundos"] = segundos
    menu["estructura"]["postres"] = postres

    todos_platos = platos_centro + segundos + postres
    analisis_global = self._analizar_menu_global(todos_platos)

    menu["analisis_temporada"] = analisis_global
    menu["marketing_tags"] = analisis_global["marketing_tags"]
    menu["porcentaje_temporada_global"] = analisis_global["porcentaje_temporada_promedio"]

    return menu


def _generar_platos_centro() -> list[dict[str, Any]]:
    """Genera los platos al centro para compartir (3 opciones)"""

    return [
        {
            "nombre": "Alcachofas fritas con lascas de foie y miel de caña",
            "descripcion": "Alcachofas de Tudela con foie gras y miel",
            "ingredientes": ["alcachofa", "foie gras", "miel", "aceite", "sal"],
            "precio": 14.00,
            "tiempo": "25 min",
            "tendencia": "gourmet",
        },
        {
            "nombre": "Croquetas de chuletón navarro",
            "descripcion": "Croquetas cremosas con carne de chuletón",
            "ingredientes": ["chuletón", "bechamel", "pan rallado", "aceite", "nuez moscada"],
            "precio": 12.00,
            "tiempo": "30 min",
            "tendencia": "tendencia",
        },
        {
            "nombre": "Carpaccio de tomate rosa de Tudela con ventresca y emulsión de piparras",
            "descripcion": "Tomate rosa con ventresca de bonito y piparras",
            "ingredientes": ["tomate rosa", "ventresca", "piparras", "aceite", "limón"],
            "precio": 13.00,
            "tiempo": "15 min",
            "tendencia": "moderno",
        },
    ]


def _generar_segundos() -> list[dict[str, Any]]:
    """Genera los segundos platos (5 opciones)"""

    return [
        {
            "nombre": "Solomillo de ternera navarra a baja temperatura",
            "descripcion": "Solomillo madurado cocido lentamente",
            "ingredientes": ["solomillo ternera", "vino tinto", "romero", "ajo", "aceite"],
            "precio": 18.00,
            "tiempo": "40 min",
            "tendencia": "baja temperatura",
        },
        {
            "nombre": "Lubina a la espalda con refrito de verduras navarras",
            "descripcion": "Pescado de lonja con verduras frescas",
            "ingredientes": ["lubina", "espárrago", "pimiento", "ajo", "aceite"],
            "precio": 16.00,
            "tiempo": "25 min",
            "tendencia": "moderno",
        },
        {
            "nombre": "Cordero lechal navarro con patatas panaderas",
            "descripcion": "Cordero local asado con patatas",
            "ingredientes": ["cordero lechal", "patata", "romero", "ajo", "aceite"],
            "precio": 17.00,
            "tiempo": "35 min",
            "tendencia": "tradicional",
        },
        {
            "nombre": "Risotto de setas de Navarra con parmesano",
            "descripcion": "Arroz cremoso con setas locales",
            "ingredientes": ["arroz", "boletus", "níscalos", "parmesano", "vino blanco"],
            "precio": 15.00,
            "tiempo": "30 min",
            "tendencia": "moderno",
        },
        {
            "nombre": "Pez de roca con mojo verde navarro",
            "descripcion": "Pescado fresco con salsa verde local",
            "ingredientes": ["pez roca", "perejil", "ajo", "vinagre", "aceite"],
            "precio": 14.50,
            "tiempo": "20 min",
            "tendencia": "innovador",
        },
    ]


def _generar_postres() -> list[dict[str, Any]]:
    """Genera los postres (3 opciones)"""

    return [
        {
            "nombre": "Tarta de queso de Idiazábal con membrillo",
            "descripcion": "Tarta cremosa con queso navarro y membrillo",
            "ingredientes": ["queso idiazábal", "membrillo", "nata", "azúcar", "galletas"],
            "precio": 6.00,
            "tiempo": "40 min",
            "tendencia": "tradicional",
        },
        {
            "nombre": "Couant de chocolate con naranjas de Navarra",
            "descripcion": "Bizcocho de chocolate con naranjas frescas",
            "ingredientes": ["chocolate", "naranja", "harina", "huevos", "mantequilla"],
            "precio": 5.50,
            "tiempo": "35 min",
            "tendencia": "clásico",
        },
        {
            "nombre": "Panna cotta de fresas de temporada",
            "descripcion": "Postre italiano con fresas navarras",
            "ingredientes": ["nata", "fresa", "azúcar", "gelatina", "vainilla"],
            "precio": 5.00,
            "tiempo": "25 min",
            "tendencia": "moderno",
        },
    ]

    def _analizar_menu_global(self, platos: list[dict[str, Any]]) -> dict[str, Any]:
        """Analiza el porcentaje de temporada de todo el menú"""
        analisis_platos = []
        total_temporada = 0
        total_ingredientes = 0
        marketing_tags = []
        alertas_globales = []

        for plato in platos:
            analisis = self.analizar_receta_temporada(plato)
            analisis_platos.append(analisis)

            total_temporada += analisis["porcentaje_temporada"] * len(plato["ingredientes"])
            total_ingredientes += len(plato["ingredientes"])

            marketing_tags.extend(analisis["marketing_tags"])
            alertas_globales.extend(analisis["alertas"])

        porcentaje_temporada_promedio = (
            (total_temporada / total_ingredientes) if total_ingredientes > 0 else 0
        )

        return {
            "analisis_platos": analisis_platos,
            "porcentaje_temporada_promedio": porcentaje_temporada_promedio,
            "cumple_soberania_global": porcentaje_temporada_promedio
            >= (self.porcentaje_minimo_temporada * 100),
            "marketing_tags": list(set(marketing_tags)),  # Eliminar duplicados
            "alertas_globales": alertas_globales,
            "total_platos_analizados": len(platos),
            "total_ingredientes_analizados": total_ingredientes,
        }

    def _obtener_productos_temporada_actual(self) -> list[dict[str, Any]]:
        """Obtiene lista de productos de temporada actual"""
        productos = []
        productos_estrella = self.calendario.get("calendario_estacional_navarra", {}).get(
            "productos_estrella", {}
        )
        productos_mes = productos_estrella.get(self.mes_espanol, {})

        for _categoria, items in productos_mes.items():
            productos.extend(items)

        # Añadir productos permanentes
        productos_permanentes = self.calendario.get("calendario_estacional_navarra", {}).get(
            "productos_permanentes", {}
        )
        for _categoria, items in productos_permanentes.items():
            productos.extend(items)

        return productos

    def generar_escandallos(self, menu: dict[str, Any]) -> dict[str, Any]:
        """Genera escandallos de costes para el menú"""
        escandallos = {
            "menu_nombre": menu["nombre"],
            "precio_venta": menu["precio"],
            "escandallos_platos": [],
            "coste_total_estimado": 0.0,
            "margen_beneficio": 0.0,
            "porcentaje_coste": 0.0,
        }

        coste_total = 0.0

        # Analizar cada sección del menú
        for _seccion, platos in menu["estructura"].items():
            for plato in platos:
                escandallo_plato = self._calcular_escandallo_plato(plato)
                escandallos["escandallos_platos"].append(escandallo_plato)
                coste_total += escandallo_plato["coste_ingredientes"]

        escandallos["coste_total_estimado"] = coste_total
        escandallos["porcentaje_coste"] = (coste_total / menu["precio"]) * 100
        escandallos["margen_beneficio"] = ((menu["precio"] - coste_total) / menu["precio"]) * 100

        return escandallos

    def _calcular_escandallo_plato(self, plato: dict[str, Any]) -> dict[str, Any]:
        """Calcula escandallo de un plato individual"""
        ingredientes = plato["ingredientes"]
        precio_venta = plato["precio"]

        coste_ingredientes = 0.0
        costes_detalle = []

        for ingrediente in ingredientes:
            analisis = self.verificar_temporada_ingrediente(ingrediente)

            # Coste base estimado (valores aproximados)
            coste_base = self._estimar_coste_ingrediente(ingrediente, analisis)

            # Añadir coste extra si no es de temporada
            if not analisis.es_temporada:
                coste_base *= 1 + analisis.coste_extra

            coste_ingredientes += coste_base
            costes_detalle.append(
                {
                    "ingrediente": ingrediente,
                    "es_temporada": analisis.es_temporada,
                    "origen": analisis.origen,
                    "coste_unitario": coste_base,
                    "coste_extra": analisis.coste_extra if not analisis.es_temporada else 0.0,
                }
            )

        porcentaje_coste = (coste_ingredientes / precio_venta) * 100

        return {
            "nombre_plato": plato["nombre"],
            "precio_venta": precio_venta,
            "coste_ingredientes": coste_ingredientes,
            "porcentaje_coste": porcentaje_coste,
            "margen_plato": precio_venta - coste_ingredientes,
            "costes_detalle": costes_detalle,
            "cumple_objetivo": porcentaje_coste <= 35,  # Objetivo: coste máximo 35%
        }

    def _estimar_coste_ingrediente(
        self, ingrediente: str, analisis: IngredientesTemporada
    ) -> float:
        """Estima el coste de un ingrediente"""
        # Costes base estimados por ingrediente (valores aproximados)
        costes_base = {
            "espárrago": 0.15,
            "guisante": 0.08,
            "lechuga": 0.05,
            "jamón": 0.30,
            "fresa": 0.12,
            "queso": 0.25,
            "nueces": 0.20,
            "tomate": 0.08,
            "pimiento": 0.10,
            "cebolla": 0.06,
            "ajo": 0.04,
            "aceite": 0.05,
            "rabo de toro": 0.45,
            "patata": 0.06,
            "trufa": 1.50,
            "vino": 0.15,
            "zanahoria": 0.05,
            "lomo": 0.35,
            "merluza": 0.40,
            "pollo": 0.25,
            "huevo": 0.12,
            "nata": 0.20,
            "azúcar": 0.08,
            "harina": 0.04,
            "mantequilla": 0.15,
            "miel": 0.25,
            "alcachofa": 0.20,
            "foie": 2.00,
            "chuletón": 0.50,
            "ventresca": 0.35,
            "piparra": 0.15,
            "limón": 0.08,
            "solomillo": 0.60,
            "lubina": 0.45,
            "cordero": 0.55,
            "arroz": 0.06,
            "boletus": 1.20,
            "níscalo": 0.80,
            "parmesano": 0.30,
            "membrillo": 0.15,
            "chocolate": 0.25,
            "naranja": 0.10,
            "gelatina": 0.08,
            "vainilla": 0.20,
            "perejil": 0.03,
            "romero": 0.04,
            "nuez moscada": 0.08,
            "pan": 0.04,
            "pan rallado": 0.06,
            "galletas": 0.08,
            "vinagre": 0.05,
            "vinagreta": 0.08,
        }

        # Buscar coste base
        for key, coste in costes_base.items():
            if key in ingrediente.lower():
                return coste

        # Coste por defecto
        return 0.10

    def guardar_menu_semanal(self, menu: dict[str, Any], escandallos: dict[str, Any]) -> str:
        """Guarda el menú semanal en formato markdown"""

        contenido_md = self._generar_markdown_menu(menu, escandallos)

        # Guardar archivo
        ruta_menu = self.base_path / "menues_semanales.md"
        with open(ruta_menu, "w", encoding="utf-8") as f:
            f.write(contenido_md)

        self.logger.info(f"Menú semanal guardado en {ruta_menu}")
        return str(ruta_menu)

    def _generar_markdown_menu(self, menu: dict[str, Any], escandallos: dict[str, Any]) -> str:
        """Genera el contenido markdown del menú"""

        contenido = f"""# {menu["nombre"]}

**Fecha:** {datetime.now().strftime("%d/%m/%Y")}
**Precio:** {menu["precio"]}EUR
**Temporada:** {menu["mes_actual"].title()}
**Porcentaje de productos de temporada:** {menu["porcentaje_temporada_global"]:.1f}%

---

## **Marketing Estacional**

{chr(10).join(f"  {tag}" for tag in menu["marketing_tags"])}

---

## **{menu["nombre"].upper()}**

"""

        # Generar sección según tipo de menú
        if menu["tipo"] == "dia":
            contenido += self._generar_seccion_menu_dia(menu)
        else:
            contenido += self._generar_seccion_menu_fin_semana(menu)

        # Añadir escandallos
        contenido += self._generar_seccion_escandallos(escandallos)

        # Añadir análisis de temporada
        contenido += self._generar_seccion_analisis_temporada(menu)

        return contenido

    def _generar_seccion_menu_dia(self, menu: dict[str, Any]) -> str:
        """Genera sección para menú del día"""
        contenido = """
### **PRIMEROS PLATOS** (Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["primeros"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        contenido += """
### **SEGUNDOS PLATOS** (Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["segundos"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        contenido += """
### **POSTRES** (Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["postres"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        return contenido

    def _generar_seccion_menu_fin_semana(self, menu: dict[str, Any]) -> str:
        """Genera sección para menú fin de semana"""
        contenido = """
### **PLATOS AL CENTRO** (Para compartir - Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["platos_centro"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        contenido += """
### **SEGUNDOS PLATOS** (Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["segundos"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        contenido += """
### **POSTRES** (Elige 1)

"""

        for i, plato in enumerate(menu["estructura"]["postres"], 1):
            analisis = next(
                a
                for a in menu["analisis_temporada"]["analisis_platos"]
                if a["nombre_receta"] == plato["nombre"]
            )
            temporada_icon = "  " if analisis["cumple_soberania"] else "  "

            contenido += f"""**{i}. {plato["nombre"]}** {temporada_icon}
{plato["descripcion"]}
_Ingredientes: {", ".join(plato["ingredientes"])}_
_Precio: {plato["precio"]}EUR | Tiempo: {plato["tiempo"]} | Tendencia: {plato["tendencia"]}_

"""

        return contenido

    def _generar_seccion_escandallos(self, escandallos: dict[str, Any]) -> str:
        """Genera sección de escandallos"""
        contenido = """
---

## **ESCANDALLOS DE COSTES**

**Coste total estimado:** {coste_total:.2f}EUR
**Porcentaje sobre precio:** {porcentaje_coste:.1f}%
**Margen de beneficio:** {margen_beneficio:.1f}%

### **Detalle por Plato**

""".format(
            coste_total=escandallos["coste_total_estimado"],
            porcentaje_coste=escandallos["porcentaje_coste"],
            margen_beneficio=escandallos["margen_beneficio"],
        )

        for escandallo in escandallos["escandallos_platos"]:
            objetivo_icon = "  " if escandallo["cumple_objetivo"] else "  "

            contenido += f"""**{escandallo["nombre_plato"]}** {objetivo_icon}
- Precio venta: {escandallo["precio_venta"]}EUR
- Coste ingredientes: {escandallo["coste_ingredientes"]:.2f}EUR ({escandallo["porcentaje_coste"]:.1f}%)
- Margen: {escandallo["margen_plato"]:.2f}EUR

"""

        return contenido

    def _generar_seccion_analisis_temporada(self, menu: dict[str, Any]) -> str:
        """Genera sección de análisis de temporada"""
        analisis = menu["analisis_temporada"]

        contenido = """
---

## **ANÁLISIS DE SOBERANÍA TEMPORADA**

**Porcentaje promedio de temporada:** {porcentaje:.1f}%
**Requisito mínimo:** 80%
**Estado:** {estado}

### **Alertas**

""".format(
            porcentaje=analisis["porcentaje_temporada_promedio"],
            estado="CUMPLE" if analisis["cumple_soberania_global"] else "NO CUMPLE",
        )

        if analisis["alertas_globales"]:
            for alerta in analisis["alertas_globales"]:
                contenido += f"- {alerta}\n"
        else:
            contenido += (
                "- No hay alertas. Todos los platos cumplen con los requisitos de temporada.\n"
            )

        contenido += f"""
### **Marketing Estacional Aplicable**

{chr(10).join(f"- {tag}" for tag in analisis["marketing_tags"])}

---

**Generado por Agente de Cocina Navarra Temporada**
**Fecha:** {datetime.now().strftime("%d/%m/%Y %H:%M")}
**Principio:** 80% de ingredientes de temporada local garantizado

"""

        return contenido


# Función principal para demostración
def demo_agente_cocina_navarra():
    """Demostración del agente de cocina navarra temporada"""
    print("AGENTE COCINA NAVARRA TEMPORADA - DEMOSTRACIÓN")
    print("=" * 50)

    # Inicializar agente
    agente = AgenteCocinaNavarraTemporada()

    print(f"Mes actual: {agente.mes_espanol.title()}")
    print(f"Porcentaje mínimo temporada: {agente.porcentaje_minimo_temporada * 100}%")
    print()

    # Generar menú del día
    print("Generando MENÚ DEL DÍA (17EUR)...")
    menu_dia = agente.generar_menu_temporada(17.0, "dia")

    print(f"Porcentaje de temporada: {menu_dia['porcentaje_temporada_global']:.1f}%")
    print(f"Marketing tags: {', '.join(menu_dia['marketing_tags'])}")
    print()

    # Generar menú fin de semana
    print("Generando MENÚ FIN DE SEMANA (22EUR)...")
    menu_fin_semana = agente.generar_menu_temporada(22.0, "fin_semana")

    print(f"Porcentaje de temporada: {menu_fin_semana['porcentaje_temporada_global']:.1f}%")
    print(f"Marketing tags: {', '.join(menu_fin_semana['marketing_tags'])}")
    print()

    # Generar escandallos
    print("Generando escandallos...")
    escandallos_dia = agente.generar_escandallos(menu_dia)
    escandallos_fin_semana = agente.generar_escandallos(menu_fin_semana)

    print(f"Coste total menú día: {escandallos_dia['coste_total_estimado']:.2f}EUR")
    print(f"Margen beneficio menú día: {escandallos_dia['margen_beneficio']:.1f}%")
    print(f"Coste total menú fin semana: {escandallos_fin_semana['coste_total_estimado']:.2f}EUR")
    print(f"Margen beneficio menú fin semana: {escandallos_fin_semana['margen_beneficio']:.1f}%")
    print()

    # Guardar menús
    print("Guardando menús...")
    ruta_menu_dia = agente.guardar_menu_semanal(menu_dia, escandallos_dia)
    print(f"Menú del día guardado en: {ruta_menu_dia}")

    # Guardar escandallos en JSON
    costes_menu = {
        "menu_dia": escandallos_dia,
        "menu_fin_semana": escandallos_fin_semana,
        "fecha_generacion": datetime.now().isoformat(),
        "mes_actual": agente.mes_espanol,
    }

    ruta_costes = agente.base_path / "costes_menu.json"
    with open(ruta_costes, "w", encoding="utf-8") as f:
        json.dump(costes_menu, f, indent=2, ensure_ascii=False)

    print(f"Escandallos guardados en: {ruta_costes}")
    print()
    print("¡MENÚS GENERADOS CON ÉXITO!")
    print("Command (P) + P: Abrir menues_semanales.md")
    print("Command + Shift + V: Vista previa del diseño")

    def procesar(self, texto: str) -> str:
        """Procesar consulta para IngredientesTemporada."""
        texto.lower()
        return f"Agente IngredientesTemporada procesando: {texto}"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para IngredientesTemporada."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para IngredientesTemporada."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para IngredientesTemporada."""
        return self.procesar(texto)


if __name__ == "__main__":
    demo_agente_cocina_navarra()
