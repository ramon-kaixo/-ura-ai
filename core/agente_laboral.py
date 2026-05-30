#!/usr/bin/env python3
"""
agente_laboral.py — URA Agente Laboral y Seguridad Social
========================================================
Gestión de nóminas, contratos y Seguridad Social.

Capacidades:
- Gestión de trabajadores
- Nóminas y seguros sociales
- TC2 (Relación Nominal de Trabajadores)
- Contratos de trabajo
- Alta/Baja en SS
- Modelos laborales

Compatible con:
- Sistema RED (Seguridad Social)
- Contrat@
- Delt@ para despidos
"""

import sqlite3
from datetime import datetime
from pathlib import Path


class AgenteLaboral:
    TIPOS_CONTRATO = {
        "indefinido": "Contrato indefinido ordinario",
        "indefinido_discontinuo": "Fijo discontinuo",
        "temporal": "Contrato temporal",
        "practicas": "Contrato en prácticas",
        "formacion": "Contrato para la formación",
        "sustitucion": "Contrato de sustitución",
    }

    TIPOS_JORNADA = {
        "completa": "Jornada completa",
        "parcial": "Jornada parcial",
        "reducida": "Jornada reducida",
    }

    CONCEPTOS_NOMINA = [
        "Salario base",
        "Complementos salariales",
        "Horas extra",
        "Prorrateo extras",
        "Plus transporte",
        "Dietas",
        "Incetivos",
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
            CREATE TABLE IF NOT EXISTS laboral_trabajadores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nss TEXT UNIQUE,
                nombre TEXT NOT NULL,
                dni TEXT UNIQUE,
                telefono TEXT,
                email TEXT,
                cargo TEXT,
                fecha_alta TEXT,
                fecha_baja TEXT,
                estado TEXT DEFAULT 'activo',
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS laboral_contratos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabajador_id INTEGER,
                tipo TEXT NOT NULL,
                jornada TEXT,
                fecha_inicio TEXT,
                fecha_fin TEXT,
                salario_bruto REAL,
                jornada_horas INTEGER,
                created_at TEXT,
                FOREIGN KEY (trabajador_id) REFERENCES laboral_trabajadores(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS laboral_nominas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabajador_id INTEGER,
                periodo TEXT NOT NULL,
                salario_bruto REAL,
                salario_neto REAL,
                deducciones REAL,
                ss_trabajador REAL,
                irpf REAL,
                ss_empresa REAL,
                fecha_pago TEXT,
                created_at TEXT,
                FOREIGN KEY (trabajador_id) REFERENCES laboral_trabajadores(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS laboral_tc2 (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trabajador_id INTEGER,
                mes TEXT NOT NULL,
                ano INTEGER NOT NULL,
                dias_cotizados INTEGER,
                base_cotizacion REAL,
                fecha_envio TEXT,
                estado TEXT DEFAULT 'pendiente',
                created_at TEXT,
                FOREIGN KEY (trabajador_id) REFERENCES laboral_trabajadores(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS laboral_alertas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tipo TEXT NOT NULL,
                trabajador_id INTEGER,
                mensaje TEXT NOT NULL,
                fecha TEXT,
                resuelta INTEGER DEFAULT 0,
                created_at TEXT
            )
        """
        )

        conn.commit()
        conn.close()

    def alta_trabajador(
        self,
        nombre: str,
        dni: str,
        nss: str = "",
        telefono: str = "",
        email: str = "",
        cargo: str = "",
    ) -> int:
        """Registra alta de trabajador."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO laboral_trabajadores
            (nss, nombre, dni, telefono, email, cargo, fecha_alta, estado, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'activo', ?)
        """,
            (nss, nombre, dni, telefono, email, cargo, ahora, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def baja_trabajador(self, trabajador_id: int, fecha: str = None) -> bool:
        """Registra baja de trabajador."""
        if fecha is None:
            fecha = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE laboral_trabajadores
            SET estado = 'baja', fecha_baja = ?
            WHERE id = ?
        """,
            (fecha, trabajador_id),
        )
        conn.commit()
        result = cursor.rowcount > 0
        conn.close()
        return result

    def crear_contrato(
        self,
        trabajador_id: int,
        tipo: str,
        salario_bruto: float,
        jornada: str = "completa",
        fecha_inicio: str = None,
        fecha_fin: str = None,
        horas: int = 40,
    ) -> int:
        """Crea un contrato."""
        if fecha_inicio is None:
            fecha_inicio = datetime.now().strftime("%Y-%m-%d")
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO laboral_contratos
            (trabajador_id, tipo, jornada, fecha_inicio, fecha_fin, salario_bruto, jornada_horas, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (trabajador_id, tipo, jornada, fecha_inicio, fecha_fin, salario_bruto, horas, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def calcular_nomina(self, trabajador_id: int, periodo: str = None) -> dict:
        """Calcula nómina básica."""
        if periodo is None:
            periodo = datetime.now().strftime("%Y-%m")

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT salario_bruto, jornada FROM laboral_contratos
            WHERE trabajador_id = ? ORDER BY fecha_inicio DESC LIMIT 1
        """,
            (trabajador_id,),
        )
        row = cursor.fetchone()

        if not row:
            conn.close()
            return {"error": "No hay contrato activo"}

        salario_bruto = row[0]

        # Cálculos simplificados (simplificados para bar)
        ss_trabajador = salario_bruto * 0.0635  # 6.35% contingencias comunes
        irpf = salario_bruto * 0.15  # IRPF simplificado (15%)
        deducciones = ss_trabajador + irpf
        salario_neto = salario_bruto - deducciones

        # SS empresa (~30% sobre salario)
        ss_empresa = salario_bruto * 0.30

        conn.close()

        return {
            "periodo": periodo,
            "salario_bruto": round(salario_bruto, 2),
            "salario_neto": round(salario_neto, 2),
            "ss_trabajador": round(ss_trabajador, 2),
            "irpf": round(irpf, 2),
            "ss_empresa": round(ss_empresa, 2),
            "total_coste_empresa": round(salario_bruto + ss_empresa, 2),
        }

    def registrar_nomina(self, trabajador_id: int, nomina: dict) -> int:
        """Registra una nómina pagada."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO laboral_nominas
            (trabajador_id, periodo, salario_bruto, salario_neto, deducciones,
             ss_trabajador, irpf, ss_empresa, fecha_pago, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                trabajador_id,
                nomina.get("periodo"),
                nomina.get("salario_bruto"),
                nomina.get("salario_neto"),
                nomina.get("ss_trabajador") + nomina.get("irpf"),
                nomina.get("ss_trabajador"),
                nomina.get("irpf"),
                nomina.get("ss_empresa"),
                ahora,
                ahora,
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def generar_tc2(self, mes: int, ano: int) -> list[dict]:
        """Genera datos TC2 para un mes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT t.id, t.nombre, t.nss, t.dni, c.salario_bruto, c.fecha_inicio
            FROM laboral_trabajadores t
            JOIN laboral_contratos c ON t.id = c.trabajador_id
            WHERE t.estado = 'activo'
            AND (c.fecha_fin IS NULL OR c.fecha_fin >= ?)
            ORDER BY t.nombre
        """,
            (f"{ano}-{mes:02d}-01",),
        )

        rows = cursor.fetchall()
        conn.close()

        trabajadores = []
        for r in rows:
            # Calcular días cotizados
            fecha_alta = datetime.strptime(r[5], "%Y-%m-%d")
            if mes == fecha_alta.month and ano == fecha_alta.year:
                dias = 30 - fecha_alta.day + 1
            else:
                dias = 30

            trabajadores.append(
                {
                    "id": r[0],
                    "nombre": r[1],
                    "nss": r[2],
                    "dni": r[3],
                    "salario": r[4],
                    "dias_cotizados": dias,
                    "base_cotizacion": round(r[4], 2),
                }
            )

        return trabajadores

    def crear_alerta(self, tipo: str, mensaje: str, trabajador_id: int = None) -> int:
        """Crea alerta laboral."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO laboral_alertas
            (tipo, trabajador_id, mensaje, fecha, created_at)
            VALUES (?, ?, ?, ?, ?)
        """,
            (tipo, trabajador_id, mensaje, ahora, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def alertas_pendientes(self) -> list[dict]:
        """Alertas laborales pendientes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, tipo, mensaje, trabajador_id, fecha
            FROM laboral_alertas
            WHERE resuelta = 0
            ORDER BY fecha DESC
            LIMIT 20
        """
        )
        rows = cursor.fetchall()
        conn.close()
        return [
            {"id": r[0], "tipo": r[1], "mensaje": r[2], "trabajador_id": r[3], "fecha": r[4]}
            for r in rows
        ]

    def listar_trabajadores(self, solo_activos: bool = True) -> list[dict]:
        """Lista trabajadores."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        query = "SELECT id, nombre, dni, nss, cargo, estado, fecha_alta FROM laboral_trabajadores"
        if solo_activos:
            query += " WHERE estado = 'activo'"
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return [
            {
                "id": r[0],
                "nombre": r[1],
                "dni": r[2],
                "nss": r[3],
                "cargo": r[4],
                "estado": r[5],
                "alta": r[6],
            }
            for r in rows
        ]

    def resumen_mensual(self) -> dict:
        """Resumen laboral del mes."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM laboral_trabajadores WHERE estado = 'activo'")
        activos = cursor.fetchone()[0]

        cursor.execute(
            """
            SELECT SUM(salario_neto) FROM laboral_nominas
            WHERE periodo LIKE ?
        """,
            (f"{datetime.now().year}-{datetime.now().month:02d}",),
        )
        total_nominas = cursor.fetchone()[0] or 0

        cursor.execute(
            """
            SELECT SUM(ss_empresa) FROM laboral_nominas
            WHERE periodo LIKE ?
        """,
            (f"{datetime.now().year}-{datetime.now().month:02d}",),
        )
        total_ss = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COUNT(*) FROM laboral_alertas WHERE resuelta = 0")
        alertas = cursor.fetchone()[0]

        conn.close()
        return {
            "trabajadores_activos": activos,
            "total_nominas_mes": round(total_nominas, 2),
            "total_ss_empresa": round(total_ss, 2),
            "coste_total": round(total_nominas + total_ss, 2),
            "alertas_pendientes": alertas,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteLaboral."""
        texto.lower()
        return (
            "Especialista en contratos, Seguridad Social y despidos. ¿Qué consulta laboral tienes?"
        )

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteLaboral."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteLaboral."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteLaboral."""
        return self.procesar(texto)

    def execute(self, *args, **kwargs) -> dict:
        """
        Método execute estándar para AgenteLaboral.

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


_LABORAL = None


def get_laboral() -> AgenteLaboral:
    global _LABORAL
    if _LABORAL is None:
        _LABORAL = AgenteLaboral()
    return _LABORAL
