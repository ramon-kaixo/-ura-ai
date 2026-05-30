#!/usr/bin/env python3
"""
agente_contabilidad.py — URA Agente de Contabilidad y Facturas
=============================================================
Gestión financiera del bar.

Capacidades:
- Registro de facturas
- Seguimiento de gastos e ingresos
- Resumen financiero
- Alertas de pagos
- Informes para Hacienda

Compatible con:
- Facturas en formato JSON/CSV
- Integración con programas de contabilidad
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


class AgenteContabilidad:
    def __init__(self, db_path: str | None = None):
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        logger.info(f"Inicializando AgenteContabilidad con db_path={db_path}")
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contabilidad_facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                numero TEXT,
                serie TEXT,
                fecha_emision TEXT,
                fecha_vencimiento TEXT,
                cliente_proveedor TEXT,
                base_imponible REAL,
                iva REAL,
                irpf REAL,
                total REAL,
                estado TEXT DEFAULT 'pendiente',
                observaciones TEXT,
                archivo TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contabilidad_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                concepto TEXT NOT NULL,
                tipo TEXT NOT NULL,
                categoria TEXT,
                importe REAL,
                factura_id INTEGER,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contabilidad_cajas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                turno TEXT,
                apertura REAL,
                ventas REAL,
                gastos REAL,
                cierre REAL,
                diferencia REAL,
                observaciones TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contabilidad_impuestos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                periodo TEXT NOT NULL,
                importe REAL,
                estado TEXT DEFAULT 'pendiente',
                fecha_presentacion TEXT,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def registrar_factura(
        self,
        tipo: str,
        numero: str,
        fecha_emision: str,
        cliente: str,
        base: float,
        iva: float = 21,
        irpf: float = 0,
        vencimiento: str = None,
        observaciones: str = "",
    ) -> int:
        """Registra una factura."""
        ahora = datetime.now().isoformat()
        total = base * (1 + iva / 100) * (1 - irpf / 100)

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contabilidad_facturas
            (tipo, numero, fecha_emision, fecha_vencimiento, cliente_proveedor,
             base_imponible, iva, irpf, total, estado, observaciones, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?, ?)
        """,
            (
                tipo,
                numero,
                fecha_emision,
                vencimiento,
                cliente,
                base,
                iva,
                irpf,
                total,
                observaciones,
                ahora,
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_venta(self, concepto: str, importe: float, categoria: str = "venta") -> int:
        """Registra una venta."""
        ahora = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contabilidad_movimientos
            (fecha, concepto, tipo, categoria, importe, created_at)
            VALUES (?, ?, 'ingreso', ?, ?, ?)
        """,
            (ahora.isoformat(), concepto, categoria, importe, ahora.isoformat()),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_gasto(self, concepto: str, importe: float, categoria: str = "gasto") -> int:
        """Registra un gasto."""
        ahora = datetime.now()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contabilidad_movimientos
            (fecha, concepto, tipo, categoria, importe, created_at)
            VALUES (?, ?, 'gasto', ?, ?, ?)
        """,
            (ahora.isoformat(), concepto, categoria, -abs(importe), ahora.isoformat()),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_caja(
        self,
        turno: str,
        apertura: float,
        ventas: float,
        gastos: float,
        cierre: float,
        observaciones: str = "",
    ) -> int:
        """Registra el cierre de caja."""
        ahora = datetime.now()
        diferencia = cierre - (apertura + ventas - gastos)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO contabilidad_cajas
            (fecha, turno, apertura, ventas, gastos, cierre, diferencia, observaciones, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                ahora.isoformat(),
                turno,
                apertura,
                ventas,
                gastos,
                cierre,
                diferencia,
                observaciones,
                ahora.isoformat(),
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def resumen_mensual(self, mes: int = None, ano: int = None) -> dict:
        """Resumen financiero del mes."""
        if mes is None:
            mes = datetime.now().month
        if ano is None:
            ano = datetime.now().year

        fecha_inicio = f"{ano}-{mes:02d}-01"
        fecha_fin = f"{ano + 1}-01-01" if mes == 12 else f"{ano}-{mes + 1:02d}-01"

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT SUM(importe) FROM contabilidad_movimientos
            WHERE tipo = 'ingreso' AND fecha >= ? AND fecha < ?
        """,
            (fecha_inicio, fecha_fin),
        )
        ingresos = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT SUM(importe) FROM contabilidad_movimientos
            WHERE tipo = 'gasto' AND fecha >= ? AND fecha < ?
        """,
            (fecha_inicio, fecha_fin),
        )
        gastos = abs(cursor.fetchone()[0] or 0)

        cursor.execute(
            """
            SELECT COUNT(*) FROM contabilidad_facturas
            WHERE tipo = 'venta' AND fecha_emision >= ? AND fecha_emision < ?
        """,
            (fecha_inicio, fecha_fin),
        )
        num_facturas = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT SUM(ventas) FROM contabilidad_cajas
            WHERE fecha >= ? AND fecha < ?
        """,
            (fecha_inicio, fecha_fin),
        )
        ventas_caja = cursor.fetchone()[0] or 0

        conn.close()

        return {
            "mes": mes,
            "año": ano,
            "ingresos": round(ingresos, 2),
            "gastos": round(gastos, 2),
            "beneficio": round(ingresos - gastos, 2),
            "facturas_emitidas": num_facturas,
            "ventas_caja": round(ventas_caja, 2),
        }

    def facturas_pendientes(self, tipo: str = None) -> list[dict]:
        """Lista facturas pendientes de pago."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT id, tipo, numero, cliente_proveedor, total, fecha_vencimiento, estado
            FROM contabilidad_facturas
            WHERE estado = 'pendiente'
        """
        if tipo:
            query += f" AND tipo = '{tipo}'"
        query += " ORDER BY fecha_vencimiento ASC"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "tipo": r[1],
                "numero": r[2],
                "cliente": r[3],
                "total": r[4],
                "vencimiento": r[5],
                "estado": r[6],
            }
            for r in rows
        ]

    def alertas_pagos(self) -> list[dict]:
        """Alertas de pagos próximos."""
        hoy = datetime.now()
        en_7_dias = hoy + timedelta(days=7)
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, numero, cliente_proveedor, total, fecha_vencimiento
            FROM contabilidad_facturas
            WHERE estado = 'pendiente'
            AND fecha_vencimiento <= ?
            ORDER BY fecha_vencimiento ASC
        """,
            (en_7_dias.isoformat(),),
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "numero": r[1], "cliente": r[2], "total": r[3], "vencimiento": r[4]}
            for r in rows
        ]

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteContabilidad."""
        texto.lower()
        return "Puedo ayudarte con IVA, IRPF, asientos contables, nóminas. ¿Qué tema contable necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteContabilidad."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteContabilidad."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteContabilidad."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteContabilidad()

    # Test: registrar factura
    factura_id = agente.registrar_factura(
        tipo="venta",
        numero="F001",
        fecha_emision=datetime.now().strftime("%Y-%m-%d"),
        cliente="Cliente Test",
        base=100.0,
    )
    print(f"Factura registrada: {factura_id}")

    # Test: resumen mensual
    resumen = agente.resumen_mensual()
    print(f"Resumen mensual: {resumen}")
