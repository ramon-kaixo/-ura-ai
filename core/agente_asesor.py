#!/usr/bin/env python3
"""
agente_asesor.py — URA Asesor Universal
========================================
Tu asistente para comparar, buscar y decidir.

Capacidades:
- Comparar seguros (coche, hogar, vida, salud)
- Analizar facturas (luz, agua, gas, internet)
- Comparar viajes y hoteles
- Buscar mejores precios
- Recomendaciones personalizadas

Usa web search para obtener datos actuales.
"""

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

try:
    REQUESTS_OK = True
except:
    REQUESTS_OK = False


class AgenteAsesor:
    CATEGORIAS_SEGUROS = {
        "coche": ["Rastreator", "Kelisto", "Comparador-seguros"],
        "hogar": ["Rastreator", "Helpmycash", "Ahorro"],
        "vida": ["Rastreator", "Cuidatuding", "Rastreator vida"],
        "salud": ["Rastreator", "Mutuas", "Comparador salud"],
    }

    PROVEEDORES_BASICOS = {
        "luz": ["Endesa", "Iberdrola", "Naturgy", "Repsol", "EdP"],
        "agua": ["Tus derechos agua", "Aigües de Barcelona", "Canal Isabel II"],
        "gas": ["Endesa", "Iberdrola", "Naturgy"],
        "internet": ["Movistar", "Orange", "Vodafone", "Masmóvil", "O2"],
    }

    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS asesor_consultas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                consulta TEXT NOT NULL,
                respuesta TEXT,
                fuentes TEXT,
                creada_en TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS asesor_facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                proveedor TEXT,
                importe REAL,
                fecha TEXT,
                concepto TEXT,
                imagen_path TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS asesor_comparaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                opciones TEXT,
                recomendacion TEXT,
                creada_en TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS asesor_preferencias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                categoria TEXT NOT NULL,
                clave TEXT NOT NULL,
                valor TEXT,
                updated_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def registrar_factura(
        self, tipo: str, proveedor: str, importe: float, fecha: str, concepto: str = ""
    ) -> int:
        """Registra una factura para analizar."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO asesor_facturas
            (tipo, proveedor, importe, fecha, concepto, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (tipo, proveedor, importe, fecha, concepto, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def analizar_facturas(self, tipo: str) -> dict:
        """Analiza facturas de un tipo."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT proveedor, importe, fecha FROM asesor_facturas
            WHERE tipo = ? ORDER BY fecha DESC LIMIT 12
        """,
            (tipo,),
        )
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return {"error": f"No hay facturas de {tipo}"}

        facturas = [{"proveedor": r[0], "importe": r[1], "fecha": r[2]} for r in rows]
        promedio = sum(f["importe"] for f in facturas) / len(facturas)
        maxima = max(facturas, key=lambda x: x["importe"])
        minima = min(facturas, key=lambda x: x["importe"])

        return {
            "tipo": tipo,
            "facturas": facturas,
            "promedio_mensual": round(promedio, 2),
            "maxima": maxima,
            "minima": minima,
            "total_12_meses": round(promedio * 12, 2),
            "consejo": self._consejo_factura(tipo, promedio),
        }

    def _consejo_factura(self, tipo: str, promedio: float) -> str:
        consejos = {
            "luz": f"Con un promedio de {promedio:.2f}€/mes, podrías ahorrar entre 20-40€ cambiando a tarifa indexada.",
            "agua": f"Consumo medio de {promedio:.2f}€/mes. Verifica si hay tarifas sociales disponibles.",
            "gas": f"{promedio:.2f}€/mes es el promedio. Compara precios por kWh entre proveedores.",
            "internet": f"{promedio:.2f}€/mes en internet. Revisa si tienes permanencia y compara con O2/Masmóvil.",
        }
        return consejos.get(tipo, "Compara con otros proveedores para ver si puedes ahorrar.")

    def comparar_seguros(self, tipo: str) -> dict:
        """Genera comparación de seguros."""
        if tipo not in self.CATEGORIAS_SEGUROS:
            return {"error": f"Tipo de seguro no reconocido: {tipo}"}

        return {
            "tipo": tipo,
            "categoria": "seguros",
            "proveedores_recomendados": self.CATEGORIAS_SEGUROS[tipo],
            "consejos": [
                f"Compara al menos 3 aseguradoras para {tipo}",
                "Revisa exclusiones y límites",
                "Considera franquicia vs prima",
                "Pide descuento por pagar anual",
            ],
            "comparadores": [
                {"nombre": "Rastreator", "url": "https://www.rastreator.com"},
                {"nombre": "Helpmycash", "url": "https://www.helpmycash.com"},
                {"nombre": "Kelisto", "url": "https://www.kelisto.es"},
            ],
        }

    def comparar_viajes(self, destino: str = None, fechas: str = None) -> dict:
        """Sugiere comparación de viajes."""
        return {
            "categoria": "viajes",
            "destino": destino or "no especificado",
            "fechas": fechas or "no especificadas",
            "comparadores": [
                {"nombre": "Skyscanner", "url": "https://www.skyscanner.es"},
                {"nombre": "Google Flights", "url": "https://flights.google.com"},
                {"nombre": "Booking", "url": "https://www.booking.com"},
                {"nombre": "Trivago", "url": "https://www.trivago.es"},
                {"nombre": "Rentalcars", "url": "https://www.rentalcars.com"},
            ],
            "consejos": [
                "Reserva con 2-3 semanas de antelación",
                "Compara precio directa vs agencias",
                "Verifica política de cancelación",
                "Considera seguro de cancelación",
            ],
        }

    def comparar_precios(self, producto: str) -> dict:
        """Sugiere dónde comparar precios."""
        return {
            "producto": producto,
            "comparadores": [
                {"nombre": "Idealo", "url": "https://www.idealo.es"},
                {"nombre": "Kelisto", "url": "https://www.kelisto.es"},
                {"nombre": "Google Shopping", "url": "https://shopping.google.com"},
                {"nombre": "Buyin", "url": "https://www.buyin.es"},
            ],
            "consejos": [
                "Compara precio por unidad (€/kg, €/litro)",
                "Mira opiniones de otros compradores",
                "Verifica gastos de envío",
                "Espera a rebajas o Black Friday",
            ],
        }

    def guardar_preferencia(self, categoria: str, clave: str, valor: Any) -> int:
        """Guarda una preferencia del usuario."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO asesor_preferencias
            (categoria, clave, valor, updated_at)
            VALUES (?, ?, ?, ?)
        """,
            (categoria, clave, json.dumps(valor), ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def obtener_preferencia(self, categoria: str, clave: str) -> Any | None:
        """Obtiene una preferencia."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT valor FROM asesor_preferencias
            WHERE categoria = ? AND clave = ?
        """,
            (categoria, clave),
        )
        row = cursor.fetchone()
        conn.close()
        return json.loads(row[0]) if row else None

    def guardar_consulta(
        self, categoria: str, consulta: str, respuesta: str = "", fuentes: list[str] = None
    ) -> int:
        """Guarda una consulta realizada."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO asesor_consultas
            (categoria, consulta, respuesta, fuentes, creada_en)
            VALUES (?, ?, ?, ?, ?)
        """,
            (categoria, consulta, respuesta, json.dumps(fuentes or []), ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def historial_consultas(self, dias: int = 30) -> list[dict]:
        """Historial de consultas."""
        cutoff = (datetime.now() - timedelta(days=dias)).isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, categoria, consulta, respuesta, creada_en
            FROM asesor_consultas
            WHERE creada_en >= ?
            ORDER BY creada_en DESC
            LIMIT 50
        """,
            (cutoff,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "categoria": r[1], "consulta": r[2], "respuesta": r[3], "fecha": r[4]}
            for r in rows
        ]

    def resumen_mensual(self) -> dict:
        """Resumen de actividad asesora."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM asesor_consultas")
        consultas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM asesor_facturas")
        facturas = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM asesor_comparaciones")
        comparaciones = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COALESCE(SUM(importe), 0) FROM asesor_facturas WHERE tipo = ?", ("luz",)
        )
        gasto_luz = cursor.fetchone()[0] or 0

        conn.close()
        return {
            "consultas_totales": consultas,
            "facturas_registradas": facturas,
            "comparaciones": comparaciones,
            "gasto_luz_estimado": round(gasto_luz, 2),
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteAsesor."""
        texto.lower()
        return "Puedo comparar, recomendar y ayudarte a decidir. ¿Qué necesitas comparar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteAsesor."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteAsesor."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteAsesor."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteAsesor.

        Args:
            *args: Argumentos posicionales
            **kwargs: Argumentos clave

        Returns:
            Dict con {"success": bool, "response": str, "error": str}
        """
        try:
            texto = args[0] if args else kwargs.get("texto", "")
            if not texto:
                return {"success": False, "response": "", "error": "No se proporcionó texto"}

            response = self.procesar(texto)
            return {"success": True, "response": response, "error": ""}
        except Exception as e:
            return {"success": False, "response": "", "error": str(e)}


_ASESOR = None


def get_asesor() -> AgenteAsesor:
    global _ASESOR
    if _ASESOR is None:
        _ASESOR = AgenteAsesor()
    return _ASESOR
