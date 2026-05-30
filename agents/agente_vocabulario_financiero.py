"""
AGENTE VOCABULARIO FINANCIERO - Términos de contabilidad y finanzas
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

TERMINOS_FINANCIEROS = [
    (
        "balance",
        "Estado financiero que refleja activos, pasivos y patrimonio",
        "Balance de situación anual",
        "estado financiero, situación",
    ),
    (
        "cuenta_pérdidas",
        "Estado de ingresos y gastos de la empresa",
        "Cuenta de pérdidas y ganancias",
        "PyG, resultado",
    ),
    (
        " activo",
        "Recursos controlados por la empresa con valor económico",
        "Activo circulante y fijo",
        "bien, recurso",
    ),
    (
        "pasivo",
        "Obligaciones financieras de la empresa",
        "Pasivo corriente y no corriente",
        "deuda, obligación",
    ),
    (
        "patrimonio",
        "Activos menos pasivos - valor neto de la empresa",
        "Fondos propios",
        "capital, equity",
    ),
    (
        "amortización",
        "Distribución del coste de un activo a lo largo de su vida útil",
        "Amortizar maquinaria en 10 años",
        "depreciación, desgaste",
    ),
    (
        "provisión",
        "Pasivo de importe o fecha incierta",
        "Provisión para impagados",
        "reserva, contingencia",
    ),
    (
        "cash_flow",
        "Flujo de caja - dinero entrante y saliente",
        "Mejorar el cash flow mensual",
        "flujo, tesorería",
    ),
    ("tesorería", "Dinero disponible en cuentas y caja", "Tener buena tesorería", "caja, efectivo"),
    (
        "facturas_pendientes",
        "Facturas emitadas pendientes de cobro",
        "Lista de facturas pendientes",
        "clientes, cobros",
    ),
    (
        "facturas_pagar",
        "Facturas recibidas pendientes de pago",
        "Control de facturas a pagar",
        "proveedores, pagos",
    ),
    ("prima", "Pago periódico de una póliza de seguro", "Pago de prima mensual", "seguro, póliza"),
    (
        "remuneración",
        "Pago total al trabajador (salario bruto)",
        "Remuneración anual de 30.000€",
        "salario, retribución",
    ),
    (
        "bruto",
        "Cantidad total antes de deducciones",
        "Salario bruto anual",
        "neto, antes de impuestos",
    ),
    ("neto", "Cantidad final después de deducciones", "Salario neto mensual", "bruto, líquido"),
    (
        "reverso",
        "Asiento contable que anula uno anterior",
        "Hacer un reverso de factura",
        "anulación, contrapartida",
    ),
    ("asiento", "Registro de una operación contable", "Asiento de apertura", "entrada, registro"),
    (
        "mayor",
        "Libro donde se registran todas las cuentas",
        "Libro mayor",
        "contabilidad, libro diario",
    ),
    (
        "conciliación",
        "Comparación de registros para verificar coincidencia",
        "Conciliación bancaria mensual",
        "conciliar, verificar",
    ),
    (
        "punto_equilibrio",
        "Volumen de ventas donde ingresos = gastos",
        "Alcanzar el punto de equilibrio",
        "break-even, umbral",
    ),
]


def init_vocabulario_financiero():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for termino, definicion, ejemplo, sinonimos in TERMINOS_FINANCIEROS:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
            VALUES ('financiero', ?, ?, ?, ?, ?)
        """,
            (termino, definicion, ejemplo, sinonimos, datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


def buscar_termino(termino):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT termino, definicion, ejemplo, sinonimos FROM biblioteca_vocabulario
        WHERE categoria = 'financiero' AND termino LIKE ?
    """,
        (f"%{termino}%",),
    )

    resultados = c.fetchall()
    conn.close()

    if resultados:
        return [
            {"termino": r[0], "definicion": r[1], "ejemplo": r[2], "sinonimos": r[3]}
            for r in resultados
        ]

    return [{"error": f"No encontrado: {termino}"}]


def listar_todos():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "SELECT termino, definicion FROM biblioteca_vocabulario WHERE categoria = 'financiero'"
    )

    resultados = c.fetchall()
    conn.close()

    return [{"termino": r[0], "definicion": r[1]} for r in resultados]


class AgenteVocabularioFinanciero:
    """Wrapper para AgenteVocabularioFinanciero."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioFinanciero."""
        return "Puedo definir términos financieros y contables. ¿Qué término financiero necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioFinanciero."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioFinanciero."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioFinanciero."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_vocabulario_financiero()
    print("=== Vocabulario Financiero ===")
    terminos = listar_todos()
    print(f"Total términos: {len(terminos)}")
