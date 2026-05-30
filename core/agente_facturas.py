#!/usr/bin/env python3
"""
agente_facturas.py — URA Captura de Facturas
============================================
Captura facturas desde email, fotos o manual.

Flujo:
1. Recibes factura por email/foto
2. URA la lee (OCR) o tú la introduces
3. URA la clasifica y almacena
4. Listo para exportar al contable

Métodos de entrada:
- Email forwarding
- Foto/escaneo
- Entrada manual
- Importar PDF
"""

import re
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    OCR_OK = True
except:
    OCR_OK = False


class AgenteFacturas:
    PROVINCIAS = [
        "Álava",
        "Albacete",
        "Alicante",
        "Almería",
        "Asturias",
        "Ávila",
        "Badajoz",
        "Barcelona",
        "Burgos",
        "Cáceres",
        "Cádiz",
        "Cantabria",
        "Castellón",
        "Ciudad Real",
        "Córdoba",
        "Cuenca",
        "Gerona",
        "Granada",
        "Guadalajara",
        "Guipúzcoa",
        "Huelva",
        "Huesca",
        "Islas Baleares",
        "Jaén",
        "La Coruña",
        "La Rioja",
        "Las Palmas",
        "León",
        "Lérida",
        "Lugo",
        "Madrid",
        "Málaga",
        "Murcia",
        "Navarra",
        "Orense",
        "Palencia",
        "Pontevedra",
        "Salamanca",
        "Santa Cruz de Tenerife",
        "Segovia",
        "Sevilla",
        "Soria",
        "Tarragona",
        "Teruel",
        "Toledo",
        "Valencia",
        "Valladolid",
        "Vizcaya",
        "Zamora",
        "Zaragoza",
    ]

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
            CREATE TABLE IF NOT EXISTS facturas_capturadas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero TEXT,
                serie TEXT,
                fecha_emision TEXT,
                fecha_vencimiento TEXT,
                proveedor_nombre TEXT,
                proveedor_nif TEXT,
                proveedor_direccion TEXT,
                cliente_nombre TEXT,
                cliente_nif TEXT,
                base_imponible REAL,
                iva_21 REAL,
                iva_10 REAL,
                iva_4 REAL,
                irpf REAL,
                total REAL,
                metodo_captura TEXT,
                archivo_path TEXT,
                estado TEXT DEFAULT 'pendiente',
                observaciones TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facturas_lineas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                factura_id INTEGER NOT NULL,
                descripcion TEXT,
                cantidad REAL,
                precio_unitario REAL,
                descuento REAL,
                importe REAL,
                FOREIGN KEY (factura_id) REFERENCES facturas_capturadas(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facturas_proveedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                nif TEXT,
                direccion TEXT,
                email TEXT,
                telefono TEXT,
                categoria TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def guardar_factura(self, datos: dict) -> int:
        """Guarda una factura capturada."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO facturas_capturadas
            (numero, serie, fecha_emision, fecha_vencimiento,
             proveedor_nombre, proveedor_nif, proveedor_direccion,
             cliente_nombre, cliente_nif, base_imponible,
             iva_21, iva_10, iva_4, irpf, total,
             metodo_captura, archivo_path, observaciones, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datos.get("numero"),
                datos.get("serie"),
                datos.get("fecha_emision"),
                datos.get("fecha_vencimiento"),
                datos.get("proveedor_nombre"),
                datos.get("proveedor_nif"),
                datos.get("proveedor_direccion"),
                datos.get("cliente_nombre"),
                datos.get("cliente_nif"),
                datos.get("base_imponible", 0),
                datos.get("iva_21", 0),
                datos.get("iva_10", 0),
                datos.get("iva_4", 0),
                datos.get("irpf", 0),
                datos.get("total", 0),
                datos.get("metodo", "manual"),
                datos.get("archivo_path"),
                datos.get("observaciones"),
                ahora,
            ),
        )

        factura_id = cursor.lastrowid

        for linea in datos.get("lineas", []):
            cursor.execute(
                """
                INSERT INTO facturas_lineas
                (factura_id, descripcion, cantidad, precio_unitario, descuento, importe)
                VALUES (?, ?, ?, ?, ?, ?)
            """,
                (
                    factura_id,
                    linea.get("descripcion"),
                    linea.get("cantidad", 1),
                    linea.get("precio", 0),
                    linea.get("descuento", 0),
                    linea.get("importe", 0),
                ),
            )

        conn.commit()
        conn.close()
        return factura_id

    def entrada_manual(
        self,
        numero: str,
        proveedor: str,
        fecha: str,
        base: float,
        iva: int = 21,
        total: float = None,
        observaciones: str = "",
    ) -> int:
        """Entrada manual rápida de factura."""
        if total is None:
            total = base * (1 + iva / 100)

        iva_field = f"iva_{iva}" if iva in [4, 10, 21] else "iva_21"

        datos = {
            "numero": numero,
            "proveedor_nombre": proveedor,
            "fecha_emision": fecha,
            "base_imponible": base,
            iva_field: base * iva / 100,
            "total": total,
            "metodo": "manual",
            "observaciones": observaciones,
        }

        return self.guardar_factura(datos)

    def guardar_proveedor(
        self,
        nombre: str,
        nif: str = "",
        direccion: str = "",
        email: str = "",
        telefono: str = "",
        categoria: str = "",
    ) -> int:
        """Registra un proveedor."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO facturas_proveedores
            (nombre, nif, direccion, email, telefono, categoria, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (nombre, nif, direccion, email, telefono, categoria, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def listar_proveedores(self) -> list[dict]:
        """Lista proveedores."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, nif, email, telefono, categoria
            FROM facturas_proveedores ORDER BY nombre
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "nombre": r[1],
                "nif": r[2],
                "email": r[3],
                "telefono": r[4],
                "categoria": r[5],
            }
            for r in rows
        ]

    def facturas_proveedor(self, proveedor_id: int) -> list[dict]:
        """Facturas de un proveedor."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, numero, fecha_emision, total, estado
            FROM facturas_capturadas
            WHERE proveedor_nombre IN
            (SELECT nombre FROM facturas_proveedores WHERE id = ?)
            ORDER BY fecha_emision DESC
        """,
            (proveedor_id,),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "numero": r[1], "fecha": r[2], "total": r[3], "estado": r[4]} for r in rows
        ]

    def pendientes_contabilizar(self) -> list[dict]:
        """Facturas pendientes de enviar al contable."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, numero, fecha_emision, proveedor_nombre, total, estado
            FROM facturas_capturadas
            WHERE estado = 'pendiente'
            ORDER BY fecha_emision DESC
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "numero": r[1],
                "fecha": r[2],
                "proveedor": r[3],
                "total": r[4],
                "estado": r[5],
            }
            for r in rows
        ]

    def marcar_contabilizada(self, factura_id: int) -> bool:
        """Marca factura como enviada al contable."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE facturas_capturadas SET estado = 'contabilizada'
            WHERE id = ?
        """,
            (factura_id,),
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def resumen_mes(self, mes: int = None, ano: int = None) -> dict:
        """Resumen mensual de facturas."""
        if mes is None:
            mes = datetime.now().month
        if ano is None:
            ano = datetime.now().year

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*), SUM(total) FROM facturas_capturadas
            WHERE strftime('%Y', fecha_emision) = ?
            AND strftime('%m', fecha_emision) = ?
        """,
            (str(ano), f"{mes:02d}"),
        )

        row = cursor.fetchone()
        total_facturas = row[0] or 0
        total_importe = row[1] or 0

        cursor.execute(
            """
            SELECT COUNT(*), SUM(total) FROM facturas_capturadas
            WHERE strftime('%Y', fecha_emision) = ?
            AND strftime('%m', fecha_emision) = ?
            AND estado = 'pendiente'
        """,
            (str(ano), f"{mes:02d}"),
        )

        row = cursor.fetchone()
        pendientes = row[0] or 0
        pendientes_importe = row[1] or 0

        conn.close()
        return {
            "mes": mes,
            "año": ano,
            "total_facturas": total_facturas,
            "total_importe": round(total_importe, 2),
            "pendientes": pendientes,
            "pendientes_importe": round(pendientes_importe, 2),
            "contabilizadas": total_facturas - pendientes,
        }

    def exportar_csv(self, inicio: str, fin: str) -> str:
        """Exporta facturas a CSV para el contable."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT numero, serie, fecha_emision, proveedor_nombre, proveedor_nif,
                   base_imponible, iva_21, iva_10, iva_4, total
            FROM facturas_capturadas
            WHERE fecha_emision >= ? AND fecha_emision <= ?
            ORDER BY fecha_emision
        """,
            (inicio, fin),
        )

        rows = cursor.fetchall()
        conn.close()

        csv = "NUMERO,SERIE,FECHA,PROVEEDOR,NIF,BASE,IVA21,IVA10,IVA4,TOTAL\n"
        for r in rows:
            csv += f"{r[0]},{r[1]},{r[2]},{r[3]},{r[4]},{r[5]},{r[6]},{r[7]},{r[8]},{r[9]}\n"

        return csv

    def importar_desde_email(self, texto_email: str) -> dict | None:
        """Intenta extraer datos de factura desde texto de email."""
        datos = {}

        numero_match = re.search(r"[Ff]actura\s*[Nn]º?\s*[:\s]*([A-Z0-9/\-]+)", texto_email)
        if numero_match:
            datos["numero"] = numero_match.group(1)

        fecha_match = re.search(r"(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})", texto_email)
        if fecha_match:
            datos["fecha_emision"] = fecha_match.group(1)

        importe_match = re.search(r"[Tt]otal[:\s]*([\d.,]+)\s*€", texto_email)
        if importe_match:
            total_str = importe_match.group(1).replace(".", "").replace(",", ".")
            datos["total"] = float(total_str)

        nif_match = re.search(r"[Nn]IF\s*[:\s]*([A-Z0-9\-]+)", texto_email)
        if nif_match:
            datos["proveedor_nif"] = nif_match.group(1)

        return datos if datos else None

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteFacturas."""
        texto.lower()
        return "Puedo emitir, gestionar y cobrar facturas electrónicas. ¿Qué necesitas hacer con facturas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteFacturas."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteFacturas."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteFacturas."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteFacturas.

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


_FACTURAS = None


def get_facturas() -> AgenteFacturas:
    global _FACTURAS
    if _FACTURAS is None:
        _FACTURAS = AgenteFacturas()
    return _FACTURAS
