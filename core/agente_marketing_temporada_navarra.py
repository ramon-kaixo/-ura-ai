#!/usr/bin/env python3
"""
AGENTE MARKETING TEMPORADA NAVARRA - Marketing estacional para productos de Navarra
Destaca automáticamente productos de temporada en carteles y material promocional
Implementa marketing basado en soberanía del producto y km 0
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
class ContenidoMarketing:
    """Contenido de marketing estacional"""

    titulo: str
    descripcion: str
    tags_marketing: list[str]
    productos_destacados: list[str]
    es_temporada: bool
    impacto_visual: str
    llamada_accion: str


class AgenteMarketingTemporadaNavarra:
    """Agente de marketing especializado en productos de temporada navarra"""

    def __init__(self):
        self.logger = logging.getLogger("Agente_Marketing_Temporada_Navarra")
        self.mes_espanol = self._obtener_mes_espanol()
        self.config_marketing = self._cargar_config_marketing()

        # Rutas de archivos
        self.base_path = Path(__file__).parent.parent
        self.calendario_path = self.base_path / "data" / "calendario_navarra.json"

        # Cargar calendario estacional
        self.calendario = self._cargar_calendario()

        # Mes actual
        self.mes_actual = datetime.now().strftime("%B").lower()
        self.mes_espanol = self._obtener_mes_espanol()

        # Configuración de marketing
        self.config_marketing = self._obtener_config_marketing()

        # Paletas de colores por temporada
        self.paletas_colores = self._definir_paletas_colores()

        # Tipografías para carteles
        self.tipografias = ["Elegant", "Modern", "Rustic", "Bold", "Minimalist"]

        self.logger.info(
            f"Agente Marketing Temporada Navarra inicializado - Mes: {self.mes_espanol}"
        )

    def _cargar_calendario(self) -> dict[str, Any]:
        """Cargar calendario estacional de Navarra"""
        try:
            with open(self.calendario_path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            self.logger.error(f"Calendario no encontrado en {self.calendario_path}")
            return {"productos_estrella": {}, "reglas_soberania": {}}

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
        return meses.get(self.mes_actual, "abril")

    def _obtener_config_marketing(self) -> dict[str, Any]:
        """Obtener configuración de marketing del calendario"""
        return self.calendario.get("reglas_soberania", {})

    def _definir_paletas_colores(self) -> dict[str, list[str]]:
        """Definir paletas de colores por temporada"""
        return {
            "primavera": ["#FF6B6B", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7", "#DDA0DD"],
            "verano": ["#FF6B35", "#F7931E", "#FFC627", "#FF6B9D", "#C44569", "#524763"],
            "otoño": ["#D63031", "#74B9FF", "#A29BFE", "#FD79A8", "#FDCB6E", "#6C5CE7"],
            "invierno": ["#2D3436", "#636E72", "#B2BEC3", "#DFE6E9", "#74B9FF", "#A29BFE"],
        }

    def _obtener_temporada_visual(self) -> str:
        """Determinar temporada visual actual"""
        meses_temporada = {
            "primavera": ["marzo", "abril", "mayo"],
            "verano": ["junio", "julio", "agosto"],
            "otoño": ["septiembre", "octubre", "noviembre"],
            "invierno": ["diciembre", "enero", "febrero"],
        }

        for temporada, meses in meses_temporada.items():
            if self.mes_espanol in meses:
                return temporada

        return "primavera"  # Default

    def generar_contenido_marketing_plato(self, plato: dict[str, Any]) -> ContenidoMarketing:
        """Genera contenido marketing para un plato específico"""
        ingredientes = plato.get("ingredientes", [])

        # Analizar ingredientes de temporada
        ingredientes_temporada = []
        ingredientes_no_temporada = []

        productos_temporada = self._obtener_productos_temporada_actual()

        for ingrediente in ingredientes:
            es_temporada = self._verificar_temporada_ingrediente(ingrediente, productos_temporada)

            if es_temporada:
                ingredientes_temporada.append(ingrediente)
            else:
                ingredientes_no_temporada.append(ingrediente)

        # Calcular porcentaje de temporada
        total_ingredientes = len(ingredientes)
        porcentaje_temporada = (
            (len(ingredientes_temporada) / total_ingredientes * 100)
            if total_ingredientes > 0
            else 0
        )

        # Generar tags de marketing
        tags_marketing = self._generar_tags_marketing(ingredientes_temporada, porcentaje_temporada)

        # Crear contenido
        contenido = ContenidoMarketing(
            titulo=plato.get("nombre", "Plato del día"),
            descripcion=self._generar_descripcion_marketing(plato, ingredientes_temporada),
            tags_marketing=tags_marketing,
            productos_destacados=ingredientes_temporada,
            es_temporada=porcentaje_temporada >= 80,
            impacto_visual=self._determinar_impacto_visual(porcentaje_temporada),
            llamada_accion=self._generar_llamada_accion(porcentaje_temporada),
        )

        return contenido

    def _verificar_temporada_ingrediente(
        self, ingrediente: str, productos_temporada: list[dict[str, Any]]
    ) -> bool:
        """Verifica si un ingrediente es de temporada"""
        for producto in productos_temporada:
            if (
                producto["nombre"].lower() in ingrediente.lower()
                or ingrediente.lower() in producto["nombre"].lower()
            ):
                return True
        return False

    def _obtener_productos_temporada_actual(self) -> list[dict[str, Any]]:
        """Obtiene productos de temporada actual"""
        productos = []
        productos_mes = self.calendario.get("productos_estrella", {}).get(self.mes_espanol, {})

        for _categoria, items in productos_mes.items():
            productos.extend(items)

        # Añadir productos permanentes
        productos_permanentes = self.calendario.get("productos_permanentes", {})
        for _categoria, items in productos_permanentes.items():
            productos.extend(items)

        return productos

    def _generar_tags_marketing(
        self, ingredientes_temporada: list[str], porcentaje_temporada: float
    ) -> list[str]:
        """Genera tags de marketing basados en ingredientes de temporada"""
        tags = []

        # Tags base de soberanía
        frases_base = self.config_marketing.get("frases_marketing", [])

        if porcentaje_temporada >= 80:
            tags.extend(random.sample(frases_base, min(2, len(frases_base))))
        elif porcentaje_temporada >= 50:
            tags.append("Con productos locales")

        # Tags específicos por ingredientes
        tags_ingredientes = {
            "alcachofa": ["Estrella de Tudela", "Tesoro navarro"],
            "espárrago": ["Verde de la Ribera", "Brotes primavera"],
            "pimiento": "Piquillo de Lodosa",
            "tomate": "Rosa de Tudela",
            "borraja": "Tradicional navarra",
            "seta": "Recolectado en Navarra",
            "cordero": "Lechal navarro",
            "ternera": "Carne de montaña",
            "queso": "Artesano navarro",
            "fresa": "Dulce de Valdizarbe",
        }

        for ingrediente in ingredientes_temporada:
            for key, tag_list in tags_ingredientes.items():
                if key in ingrediente.lower():
                    if isinstance(tag_list, list):
                        tags.extend(tag_list)
                    else:
                        tags.append(tag_list)

        return list(set(tags))  # Eliminar duplicados

    def _generar_descripcion_marketing(
        self, plato: dict[str, Any], ingredientes_temporada: list[str]
    ) -> str:
        """Genera descripción marketing para el plato"""
        descripcion_base = plato.get("descripcion", "")

        if len(ingredientes_temporada) == 0:
            return descripcion_base

        # Añadir frase destacada de temporada
        frases_destacadas = [
            f"Elaborado con {len(ingredientes_temporada)} productos de nuestra tierra",
            "Sabor auténtico con ingredientes de temporada navarra",
            "Directo de la huerta navarra a tu mesa",
            "Tradición y frescura en cada bocado",
        ]

        frase_destacada = random.choice(frases_destacadas)

        return f"{descripcion_base}. {frase_destacada}."

    def _determinar_impacto_visual(self, porcentaje_temporada: float) -> str:
        """Determina el nivel de impacto visual"""
        if porcentaje_temporada >= 90:
            return "máximo"
        elif porcentaje_temporada >= 80:
            return "alto"
        elif porcentaje_temporada >= 60:
            return "medio"
        else:
            return "bajo"

    def _generar_llamada_accion(self, porcentaje_temporada: float) -> str:
        """Genera llamada a la acción"""
        if porcentaje_temporada >= 80:
            llamadas = [
                "¡Disfruta del sabor de Navarra en su mejor momento!",
                "No te pierdas estos productos de temporada limitada",
                "Sabor auténtico, solo por tiempo limitado",
                "Prueba la frescura de nuestra tierra hoy",
            ]
        else:
            llamadas = [
                "Descubre nuestros platos del día",
                "Ven a probar nuestras especialidades",
                "Te esperamos con los mejores sabores",
                "Disfruta de nuestra cocina casera",
            ]

        return random.choice(llamadas)

    def disenar_cartel_menu(self, menu: dict[str, Any]) -> dict[str, Any]:
        """Diseña cartel para menú con elementos de temporada destacados"""
        temporada_visual = self._obtener_temporada_visual()
        paleta_colores = self.paletas_colores[temporada_visual]
        tipografia = random.choice(self.tipografias)

        # Analizar platos del menú
        platos_analizados = []
        productos_destacados_global = []
        marketing_tags_global = []

        for _categoria, platos in menu["estructura"].items():
            for plato in platos:
                contenido = self.generar_contenido_marketing_plato(plato)
                platos_analizados.append({"plato": plato, "marketing": contenido})

                productos_destacados_global.extend(contenido.productos_destacados)
                marketing_tags_global.extend(contenido.tags_marketing)

        # Eliminar duplicados
        productos_destacados_global = list(set(productos_destacados_global))
        marketing_tags_global = list(set(marketing_tags_global))

        # Diseño del cartel
        disenio = {
            "nombre_menu": menu["nombre"],
            "precio": menu["precio"],
            "temporada": self.mes_espanol.title(),
            "disenio_visual": {
                "paleta_colores": paleta_colores,
                "tipografia_principal": tipografia,
                "tipografia_secundaria": self._obtener_tipografia_secundaria(tipografia),
                "layout": "moderno_rustico",
                "estilo": "navarro_temporada",
            },
            "marketing_estacional": {
                "titulo_destacado": self._generar_titulo_destacado(menu),
                "subtitulo_estacional": self._generar_subtitulo_estacional(),
                "tags_principales": marketing_tags_global[:3],  # Top 3 tags
                "productos_estrella": productos_destacados_global[:5],  # Top 5 productos
                "frase_impacto": self._generar_frase_impacto(menu),
                "llamada_accion": self._generar_llamada_accion_menu(menu),
            },
            "estructura_platos": platos_analizados,
            "elementos_graficos": self._generar_elementos_graficos(temporada_visual),
            "formato_impresion": {
                "dimensiones": "A4",
                "orientacion": "vertical",
                "resolucion": "300dpi",
                "margenes": "estandar",
            },
        }

        return disenio

    def _obtener_tipografia_secundaria(self, tipografia_principal: str) -> str:
        """Obtiene tipografía secundaria complementaria"""
        combinaciones = {
            "Elegant": "Classic",
            "Modern": "Clean",
            "Rustic": "Handwritten",
            "Bold": "Simple",
            "Minimalist": "Light",
        }
        return combinaciones.get(tipografia_principal, "Classic")

    def _generar_titulo_destacado(self, menu: dict[str, Any]) -> str:
        """Genera título destacado para el menú"""
        mes = self.mes_espanol.title()

        titulos = [
            f"SABORES DE {mes.upper()} EN NAVARRA",
            f"TEMPORADA {mes.upper()} - PRODUCTO LOCAL",
            f"{mes.upper()}: LO MEJOR DE NUESTRA TIERRA",
            f"COCINA DE {mes.upper()} - KM 0 GARANTIZADO",
        ]

        return random.choice(titulos)

    def _generar_subtitulo_estacional(self) -> str:
        """Genera subtítulo estacional"""
        subtitulos = [
            "Con productos de nuestra huerta",
            "Recién llegado de la lonja",
            "Sabor auténtico de Navarra",
            "Tradición y frescaza",
            "Directo del agricultor navarro",
        ]

        return random.choice(subtitulos)

    def _generar_frase_impacto(self, menu: dict[str, Any]) -> str:
        """Genera frase de impacto para el menú"""
        porcentaje_temporada = menu.get("porcentaje_temporada_global", 0)

        if porcentaje_temporada >= 90:
            frases = [
                "100% compromiso con los productos locales",
                "La esencia de Navarra en cada plato",
                "Temporada perfecta, sabor incomparable",
                "Nuestra tierra en su máximo esplendor",
            ]
        elif porcentaje_temporada >= 80:
            frases = [
                "80% de ingredientes de temporada garantizado",
                "El mejor sabor de nuestra tierra",
                "Tradición navarra con toque moderno",
                "Frescura y calidad en cada bocado",
            ]
        else:
            frases = [
                "Platos caseros con amor",
                "Sabor auténtico navarro",
                "Tradición culinaria",
                "Cocina con pasión",
            ]

        return random.choice(frases)

    def _generar_llamada_accion_menu(self, menu: dict[str, Any]) -> str:
        """Genera llamada a la acción para el menú"""
        tipo_menu = menu.get("tipo", "dia")

        if tipo_menu == "dia":
            llamadas = [
                "Ven a disfrutar del mejor menú del día",
                "Tu descanso, nuestra especialidad",
                "Almuerza como en casa",
                "Sabor navarro en tu pausa",
            ]
        else:
            llamadas = [
                "Celebra el fin de semana con nosotros",
                "Experiencia gastronómica superior",
                "Comparte momentos inolvidables",
                "Fin de semana, sabores únicos",
            ]

        return random.choice(llamadas)

    def _generar_elementos_graficos(self, temporada_visual: str) -> dict[str, Any]:
        """Genera elementos gráficos para el diseño"""
        elementos = {
            "primavera": {
                "iconos": ["flor", "brote", "sol", "hoja"],
                "decorados": ["ramas florales", "pétalos", "marcos orgánicos"],
                "fondo": "suave con textura de papel",
            },
            "verano": {
                "iconos": ["sol", "playa", "fruta", "refresco"],
                "decorados": ["rayos de sol", "olas", "frutas tropicales"],
                "fondo": "brillante con vibrante",
            },
            "otoño": {
                "iconos": ["hoja", "castaña", "lluvia", "cosecha"],
                "decorados": ["hojas caídas", "tonos tierra", "textura madera"],
                "fondo": "cálido con textura rustica",
            },
            "invierno": {
                "iconos": ["copo", "estrella", "fuego", "abrigo"],
                "decorados": "copos de nieve, estrellas, marcos elegantes",
                "fondo": "elegante con textura sutil",
            },
        }

        return elementos.get(temporada_visual, elementos["primavera"])

    def generar_html_cartel(self, disenio: dict[str, Any]) -> str:
        """Genera HTML para el cartel del menú"""
        colores = disenio["disenio_visual"]["paleta_colores"]
        tipografia = disenio["disenio_visual"]["tipografia_principal"]

        html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{disenio["nombre_menu"]}</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family={tipografia.replace(" ", "+")}&display=swap');

        body {{
            font-family: '{tipografia}', serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, {colores[0]}, {colores[1]});
            color: #2c3e50;
        }}

        .cartel {{
            max-width: 600px;
            margin: 0 auto;
            background: white;
            border-radius: 15px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.2);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, {colores[2]}, {colores[3]});
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .titulo {{
            font-size: 2.5em;
            margin: 0;
            font-weight: bold;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
        }}

        .subtitulo {{
            font-size: 1.2em;
            margin: 10px 0 0 0;
            opacity: 0.9;
        }}

        .marketing {{
            background: {colores[4]};
            color: white;
            padding: 20px;
            text-align: center;
        }}

        .tags {{
            display: flex;
            justify-content: center;
            flex-wrap: wrap;
            gap: 10px;
            margin: 15px 0;
        }}

        .tag {{
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            font-size: 0.9em;
            border: 1px solid rgba(255,255,255,0.3);
        }}

        .frase-impacto {{
            font-size: 1.3em;
            font-style: italic;
            margin: 15px 0;
        }}

        .contenido {{
            padding: 30px;
        }}

        .seccion {{
            margin: 30px 0;
        }}

        .seccion h2 {{
            color: {colores[2]};
            border-bottom: 3px solid {colores[3]};
            padding-bottom: 10px;
        }}

        .plato {{
            margin: 15px 0;
            padding: 15px;
            background: #f8f9fa;
            border-radius: 10px;
            border-left: 4px solid {colores[2]};
        }}

        .plato h3 {{
            margin: 0 0 5px 0;
            color: {colores[2]};
        }}

        .plato-marketing {{
            font-size: 0.9em;
            color: #666;
            font-style: italic;
            margin: 5px 0;
        }}

        .temporada {{
            color: #27ae60;
            font-weight: bold;
        }}

        .precio {{
            color: {colores[5]};
            font-weight: bold;
            font-size: 1.1em;
        }}

        .footer {{
            background: {colores[2]};
            color: white;
            padding: 20px;
            text-align: center;
        }}

        .llamada-accion {{
            font-size: 1.2em;
            font-weight: bold;
            margin: 10px 0;
        }}

        @media print {{
            body {{ background: white; }}
            .cartel {{ box-shadow: none; }}
        }}
    </style>
</head>
<body>
    <div class="cartel">
        <div class="header">
            <h1 class="titulo">{disenio["marketing_estacional"]["titulo_destacado"]}</h1>
            <p class="subtitulo">{disenio["marketing_estacional"]["subtitulo_estacional"]}</p>
        </div>

        <div class="marketing">
            <div class="tags">
                {"".join(f'<span class="tag">{tag}</span>' for tag in disenio["marketing_estacional"]["tags_principales"])}
            </div>
            <p class="frase-impacto">{disenio["marketing_estacional"]["frase_impacto"]}</p>
        </div>

        <div class="contenido">
"""

        # Añadir secciones del menú
        for categoria, platos in (
            disenio["estructura_platos"][0]["plato"].get("estructura", {}).items()
        ):
            if isinstance(platos, list) and platos:
                html += f'            <div class="seccion">\n                <h2>{categoria.upper().replace("_", " ")}</h2>\n'

                for plato_info in platos:
                    if isinstance(plato_info, dict):
                        html += f'                <div class="plato">\n                    <h3>{plato_info["nombre"]}</h3>\n'
                        html += f"                    <p>{plato_info['descripcion']}</p>\n"

                        # Buscar marketing del plato
                        marketing_plato = next(
                            (
                                p["marketing"]
                                for p in disenio["estructura_platos"]
                                if p["plato"]["nombre"] == plato_info["nombre"]
                            ),
                            None,
                        )

                        if marketing_plato and marketing_plato.es_temporada:
                            html += f'                    <p class="plato-marketing temporada">{marketing_plato.descripcion}</p>\n'

                        html += f'                    <p class="precio">{plato_info["precio"]}EUR</p>\n                </div>\n'

                html += "            </div>\n"

        html += f"""        </div>

        <div class="footer">
            <p class="llamada-accion">{disenio["marketing_estacional"]["llamada_accion"]}</p>
            <p>Temporada: {disenio["temporada"]} | Precio: {disenio["precio"]}EUR</p>
            <p>Generado por Agente Marketing Temporada Navarra</p>
        </div>
    </div>
</body>
</html>"""

        return html

    def guardar_cartel_html(self, disenio: dict[str, Any]) -> str:
        """Guarda el cartel en formato HTML"""
        html_content = self.generar_html_cartel(disenio)

        # Guardar archivo
        ruta_cartel = self.base_path / f"cartel_menu_{disenio['tipo']}.html"
        with open(ruta_cartel, "w", encoding="utf-8") as f:
            f.write(html_content)

        self.logger.info(f"Cartel guardado en {ruta_cartel}")
        return str(ruta_cartel)


# Función de demostración
def demo_agente_marketing_temporada():
    """Demostración del agente de marketing temporada"""
    print("AGENTE MARKETING TEMPORADA NAVARRA - DEMOSTRACIÓN")
    print("=" * 50)

    # Inicializar agente
    agente = AgenteMarketingTemporadaNavarra()

    print(f"Mes actual: {agente.mes_espanol.title()}")
    print(f"Temporada visual: {agente._obtener_temporada_visual()}")
    print()

    # Ejemplo de plato
    plato_ejemplo = {
        "nombre": "Menestra de verduras de la Ribera",
        "descripcion": "Verduras frescas con jamón ibérico",
        "ingredientes": ["espárrago verde", "guisante", "lechuga", "jamón ibérico"],
        "precio": 8.50,
    }

    print("Analizando marketing para plato ejemplo...")
    contenido_marketing = agente.generar_contenido_marketing_plato(plato_ejemplo)

    print(f"Título: {contenido_marketing.titulo}")
    print(f"Descripción: {contenido_marketing.descripcion}")
    print(f"Tags: {', '.join(contenido_marketing.tags_marketing)}")
    print(f"Productos destacados: {', '.join(contenido_marketing.productos_destacados)}")
    print(f"Es temporada: {contenido_marketing.es_temporada}")
    print(f"Impacto visual: {contenido_marketing.impacto_visual}")
    print(f"Llamada acción: {contenido_marketing.llamada_accion}")
    print()

    # Generar cartel para menú de ejemplo
    print("Generando diseño de cartel...")
    menu_ejemplo = {
        "nombre": "MENÚ DEL DÍA - SOBERANÍA NAVARRA",
        "precio": 17.0,
        "tipo": "dia",
        "porcentaje_temporada_global": 85.0,
        "estructura": {"primeros": [plato_ejemplo], "segundos": [], "postres": []},
    }

    disenio_cartel = agente.disenar_cartel_menu(menu_ejemplo)

    print(f"Título destacado: {disenio_cartel['marketing_estacional']['titulo_destacado']}")
    print(f"Subtitulo: {disenio_cartel['marketing_estacional']['subtitulo_estacional']}")
    print(
        f"Tags principales: {', '.join(disenio_cartel['marketing_estacional']['tags_principales'])}"
    )
    print(f"Frase impacto: {disenio_cartel['marketing_estacional']['frase_impacto']}")
    print()

    # Guardar cartel
    print("Guardando cartel HTML...")
    ruta_cartel = agente.guardar_cartel_html(disenio_cartel)
    print(f"Cartel guardado en: {ruta_cartel}")
    print()
    print("¡MARKETING TEMPORADA GENERADO CON ÉXITO!")

    def procesar(self, texto: str) -> str:
        """Procesar consulta para ContenidoMarketing."""
        texto.lower()
        return f"Agente ContenidoMarketing procesando: {texto}"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para ContenidoMarketing."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para ContenidoMarketing."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para ContenidoMarketing."""
        return self.procesar(texto)


if __name__ == "__main__":
    demo_agente_marketing_temporada()
