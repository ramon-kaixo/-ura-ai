"""
AGENTE VOCABULARIO LEGAL - Términos jurídicos y fiscales españoles
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

TERMINOS_LEGALES = [
    (
        "factura",
        "Documento mercantil que refleja una transacción comercial",
        "Emitir factura a cliente",
        "tique, albarán",
    ),
    (
        "IVA",
        "Impuesto sobre el Valor Añadido - 21% general, 10% reducido, 4% superreducido",
        "Factura con IVA incluido",
        "impuesto, tributo",
    ),
    (
        "IRPF",
        "Impuesto sobre la Renta de las Personas Físicas",
        "Retención IRPF en nómina",
        "impuesto, retención",
    ),
    (
        "autónomo",
        "Trabajador por cuenta propia dado de alta en Seguridad Social",
        "Estar dado de alta como autónomo",
        "self-employed, RETA",
    ),
    (
        "RETA",
        "Régimen Especial de Trabajadores Autónomos",
        "Cotizar al RETA",
        "autónomo, Seguridad Social",
    ),
    (
        "modelo130",
        "Declaración trimestral de IRPF para autónomos",
        "Presentar modelo 130",
        "IRPF, trimestral",
    ),
    ("modelo303", "Declaración trimestral de IVA", "Presentar modelo 303", "IVA, trimestral"),
    ("modelo390", "Declaración anual resumida de IVA", "Presentar modelo 390", "IVA, anual"),
    ("modelo180", "Resumen anual de retenciones IRPF", "Presentar modelo 180", "IRPF, anual"),
    (
        "TC2",
        "Texto CONFECOP 2 - Relación nominal de trabajadores",
        "Enviar TC2 a Seguridad Social",
        "nómina, Seguridad Social",
    ),
    (
        "TC1",
        "Texto CONFECOP 1 - Liquidación de cuotas SS",
        "Calcular TC1 mensual",
        "Seguridad Social, cuota",
    ),
    ("nómina", "Documento de pago salarial al trabajador", "Firmar la nómina", "salario, pago"),
    ("contrato", "Acuerdo legal entre partes", "Firmar contrato de trabajo", "acuerdo, pacto"),
    (
        "registro_mercantil",
        "Libro oficial donde se inscriben empresas",
        "Inscribir sociedad en Registro Mercantil",
        "RM, inscribir",
    ),
    (
        "CCC",
        "Código de Cuenta de Cotización a la Seguridad Social",
        "EI CCC de la empresa es el 123456789",
        "Seguridad Social, SS",
    ),
    (
        "epígrafe",
        "Clasificación de actividad económica en IAE",
        "Epígrafe de hosteleria",
        "IAE, actividad",
    ),
    ("IAE", "Impuesto sobre Actividades Económicas", "Dar de alta en IAE", "actividad, tributo"),
    (
        "censal",
        "Alta en el censo de empresarios de Hacienda",
        "Estar dado de alta en el censal",
        "Hacienda, alta",
    ),
    (
        "Cl@ve",
        "Sistema de identificación digital española",
        "Registrarse en Cl@ve",
        "identidad, firma digital",
    ),
    (
        "certificado_digital",
        "Firma electrónica reconocida",
        "Renovar certificado digital",
        "firma, eIDAS",
    ),
]


def init_vocabulario_legal():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for termino, definicion, ejemplo, sinonimos in TERMINOS_LEGALES:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, created_at)
            VALUES ('legal', ?, ?, ?, ?, ?)
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
        WHERE categoria = 'legal' AND termino LIKE ?
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

    c.execute("SELECT termino, definicion FROM biblioteca_vocabulario WHERE categoria = 'legal'")

    resultados = c.fetchall()
    conn.close()

    return [{"termino": r[0], "definicion": r[1]} for r in resultados]


class AgenteVocabularioLegal:
    """Wrapper para AgenteVocabularioLegal."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteVocabularioLegal."""
        return "Puedo definir términos jurídicos, BOE y sentencias. ¿Qué término legal necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteVocabularioLegal."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteVocabularioLegal."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteVocabularioLegal."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_vocabulario_legal()
    print("=== Vocabulario Legal ===")
    terminos = listar_todos()
    print(f"Total términos: {len(terminos)}")
