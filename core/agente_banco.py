#!/usr/bin/env python3
"""
agente_banco.py — URA Conciliación Bancaria
=============================================
Gestión de cuentas bancarias y conciliación.

Capacidades:
- Registrar movimientos bancarios
- Conciliar con facturas (cobros/pagos)
- Detectar discrepancias
- Exportar para contable
- Alertas de cobros pendientes

Flujo:
1. Importas extracto bancario (CSV)
2. URA compara con facturas/clientes
3. Conciliación automática cuando coincide
4. Lo que no concilia → revisión manual
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path

try:
    from core.payment_guardian import autorizar_pago

    PAYMENT_GUARDIAN_OK = True
except Exception:
    PAYMENT_GUARDIAN_OK = False

try:
    REQUESTS_OK = True
except Exception:
    REQUESTS_OK = False


class AgenteBanco:
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
            CREATE TABLE IF NOT EXISTS banco_cuentas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                banco TEXT,
                iban TEXT,
                saldo_actual REAL DEFAULT 0,
                activa INTEGER DEFAULT 1,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS banco_movimientos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cuenta_id INTEGER,
                fecha TEXT NOT NULL,
                concepto TEXT,
                importe REAL,
                tipo TEXT,
                referencia TEXT,
                conciliado INTEGER DEFAULT 0,
                factura_id INTEGER,
                created_at TEXT,
                FOREIGN KEY (cuenta_id) REFERENCES banco_cuentas(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS banco_conciliacion (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                movimiento_id INTEGER,
                factura_id INTEGER,
                tipo_enlace TEXT,
                importe_conciliado REAL,
                diferencia REAL,
                estado TEXT DEFAULT 'pendiente',
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def crear_cuenta(self, nombre: str, banco: str = "", iban: str = "", saldo: float = 0) -> int:
        """Crea una cuenta bancaria."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO banco_cuentas
            (nombre, banco, iban, saldo_actual, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (nombre, banco, iban, saldo, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_movimiento(
        self, cuenta_id: int, fecha: str, concepto: str, importe: float, referencia: str = ""
    ) -> int:
        """Registra un movimiento bancario. Los pagos (importe < 0) pasan por payment_guardian."""
        # Pagos salientes requieren autorización
        if importe < 0 and PAYMENT_GUARDIAN_OK:
            if not autorizar_pago(abs(importe), concepto, fuente="agente_banco"):
                raise PermissionError(
                    f"Pago de {abs(importe):.2f}€ rechazado o pendiente de autorización: {concepto}"
                )
        ahora = datetime.now().isoformat()
        tipo = "ingreso" if importe > 0 else "gasto"
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO banco_movimientos
            (cuenta_id, fecha, concepto, importe, tipo, referencia, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
            (cuenta_id, fecha, concepto, importe, tipo, referencia, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def importar_csv(self, cuenta_id: int, ruta_csv: str) -> dict:
        """Importa movimientos desde CSV bancario."""
        movimientos_importados = 0
        errores = []

        try:
            with open(ruta_csv, encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        fecha = row.get("fecha", row.get("date", ""))
                        concepto = row.get("concepto", row.get("description", ""))
                        importe_str = row.get("importe", row.get("amount", "0"))
                        importe = float(importe_str.replace(",", "."))
                        referencia = row.get("referencia", row.get("reference", ""))

                        self.registrar_movimiento(cuenta_id, fecha, concepto, importe, referencia)
                        movimientos_importados += 1
                    except Exception as e:
                        errores.append(str(e))

        except Exception as e:
            return {"error": f"No se pudo leer el CSV: {e}"}

        return {"importados": movimientos_importados, "errores": len(errores)}

    def conciliacion_automatica(self, cuenta_id: int, tolerancia: float = 0.50) -> list[dict]:
        """Conciliación automática movimientos vs facturas."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, fecha_emision, proveedor_nombre, total
            FROM facturas_capturadas
            WHERE estado = 'pendiente'
            ORDER BY fecha_emision DESC
        """
        )
        facturas = cursor.fetchall()

        cursor.execute(
            """
            SELECT id, fecha, concepto, importe, referencia
            FROM banco_movimientos
            WHERE cuenta_id = ? AND conciliado = 0
            ORDER BY fecha DESC
        """,
            (cuenta_id,),
        )
        movimientos = cursor.fetchall()

        conciliados = []
        for mov in movimientos:
            mov_id, mov_fecha, mov_concepto, mov_importe, mov_ref = mov

            for fac in facturas:
                fac_id, fac_fecha, fac_proveedor, fac_total = fac

                dif = abs(abs(mov_importe) - fac_total)
                if dif <= tolerancia:
                    cursor.execute(
                        """
                        UPDATE banco_movimientos SET conciliado = 1, factura_id = ?
                        WHERE id = ?
                    """,
                        (fac_id, mov_id),
                    )

                    cursor.execute(
                        """
                        INSERT INTO banco_conciliacion
                        (movimiento_id, factura_id, tipo_enlace, importe_conciliado, diferencia, estado, created_at)
                        VALUES (?, ?, ?, ?, ?, 'conciliado', ?)
                    """,
                        (mov_id, fac_id, "automatico", fac_total, dif, datetime.now().isoformat()),
                    )

                    conciliados.append(
                        {
                            "movimiento": mov_concepto,
                            "factura": fac_proveedor,
                            "importe": fac_total,
                            "diferencia": dif,
                        }
                    )
                    break

        conn.commit()
        conn.close()
        return conciliados

    def movimientos_pendientes(self, cuenta_id: int = None) -> list[dict]:
        """Movimientos sin conciliar."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = """
            SELECT m.id, m.fecha, m.concepto, m.importe, m.tipo, c.nombre
            FROM banco_movimientos m
            JOIN banco_cuentas c ON m.cuenta_id = c.id
            WHERE m.conciliado = 0
        """
        params = []
        if cuenta_id:
            query += " AND m.cuenta_id = ?"
            params.append(cuenta_id)
        query += " ORDER BY m.fecha DESC LIMIT 50"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "fecha": r[1],
                "concepto": r[2],
                "importe": r[3],
                "tipo": r[4],
                "cuenta": r[5],
            }
            for r in rows
        ]

    def marcar_conciliado_manual(self, movimiento_id: int, factura_id: int = None) -> bool:
        """Conciliación manual."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE banco_movimientos SET conciliado = 1, factura_id = ?
            WHERE id = ?
        """,
            (factura_id, movimiento_id),
        )

        if factura_id:
            cursor.execute(
                """
                INSERT INTO banco_conciliacion
                (movimiento_id, factura_id, tipo_enlace, importe_conciliado, estado, created_at)
                VALUES (?, ?, 'manual', 0, 'conciliado', ?)
            """,
                (movimiento_id, factura_id, datetime.now().isoformat()),
            )

        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def resumen_cuenta(self, cuenta_id: int) -> dict:
        """Resumen de cuenta bancaria."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT COUNT(*) FROM banco_movimientos
            WHERE cuenta_id = ? AND conciliado = 0
        """,
            (cuenta_id,),
        )
        pendientes = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT SUM(importe) FROM banco_movimientos
            WHERE cuenta_id = ? AND importe > 0
        """,
            (cuenta_id,),
        )
        total_ingresos = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT SUM(importe) FROM banco_movimientos
            WHERE cuenta_id = ? AND importe < 0
        """,
            (cuenta_id,),
        )
        total_gastos = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT saldo_actual FROM banco_cuentas WHERE id = ?
        """,
            (cuenta_id,),
        )
        saldo = cursor.fetchone()[0] or 0

        conn.close()
        return {
            "pendientes_conciliar": pendientes,
            "total_ingresos": round(total_ingresos, 2),
            "total_gastos": round(total_gastos, 2),
            "saldo_registrado": round(saldo, 2),
            "balance": round(total_ingresos + total_gastos, 2),
        }

    def listado_cuentas(self) -> list[dict]:
        """Lista cuentas bancarias."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, nombre, banco, iban, saldo_actual
            FROM banco_cuentas WHERE activa = 1
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "nombre": r[1], "banco": r[2], "iban": r[3], "saldo": r[4]} for r in rows
        ]

    def exportar_extracto(self, cuenta_id: int, inicio: str, fin: str) -> str:
        """Exporta movimientos a CSV."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT fecha, concepto, importe, tipo, conciliado
            FROM banco_movimientos
            WHERE cuenta_id = ? AND fecha >= ? AND fecha <= ?
            ORDER BY fecha
        """,
            (cuenta_id, inicio, fin),
        )
        rows = cursor.fetchall()
        conn.close()

        csv = "FECHA,CONCEPTO,IMPORTE,TIPO,CONCILIADO\n"
        for r in rows:
            csv += f"{r[0]},{r[1]},{r[2]},{r[3]},{'S' if r[4] else 'N'}\n"

        return csv

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteBanco."""
        texto.lower()
        return "Puedo conciliar cuentas, gestionar extractos bancarios y transferencias. ¿Qué operación bancaria necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteBanco."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteBanco."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteBanco."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteBanco.

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


_BANCO = None


def get_banco() -> AgenteBanco:
    global _BANCO
    if _BANCO is None:
        _BANCO = AgenteBanco()
    return _BANCO
