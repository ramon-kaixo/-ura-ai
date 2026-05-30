#!/usr/bin/env python3
"""
agente_rrhh.py — URA Agente de Recursos Humanos
==============================================
Gestión de empleados, horarios, vacaciones y nómina.

Capacidades:
- Registro de empleados
- Control de horarios
- Gestión de vacaciones
- Nómina básica
- Evaluaciones de desempeño
"""

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class AgenteRRHH:
    """Agente de Recursos Humanos."""

    def __init__(self, db_path: str | None = None):
        """Inicializar agente de RRHH."""
        if db_path is None:
            db_path = str(Path(__file__).resolve().parents[1] / "board.db")
        self.db_path = db_path
        logger.info(f"Inicializando AgenteRRHH con db_path={db_path}")
        self._init_db()

    def _init_db(self):
        """Inicializar tablas de RRHH."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rrhh_empleados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellido TEXT,
                puesto TEXT,
                departamento TEXT,
                fecha_contratacion TEXT,
                salario_base REAL,
                estado TEXT DEFAULT 'activo',
                telefono TEXT,
                email TEXT,
                created_at TEXT
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rrhh_horarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado_id INTEGER,
                fecha TEXT NOT NULL,
                hora_entrada TEXT,
                hora_salida TEXT,
                horas_trabajadas REAL,
                created_at TEXT,
                FOREIGN KEY (empleado_id) REFERENCES rrhh_empleados(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rrhh_vacaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado_id INTEGER,
                fecha_inicio TEXT NOT NULL,
                fecha_fin TEXT NOT NULL,
                dias_solicitados INTEGER,
                estado TEXT DEFAULT 'pendiente',
                motivo TEXT,
                aprobado_por TEXT,
                fecha_aprobacion TEXT,
                created_at TEXT,
                FOREIGN KEY (empleado_id) REFERENCES rrhh_empleados(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rrhh_nominas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado_id INTEGER,
                periodo TEXT NOT NULL,
                salario_base REAL,
                horas_extra REAL,
                bonificaciones REAL,
                deducciones REAL,
                total REAL,
                pagado INTEGER DEFAULT 0,
                fecha_pago TEXT,
                created_at TEXT,
                FOREIGN KEY (empleado_id) REFERENCES rrhh_empleados(id)
            )
        """
        )

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS rrhh_evaluaciones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado_id INTEGER,
                fecha_evaluacion TEXT NOT NULL,
                evaluador TEXT,
                puntaje INTEGER,
                comentarios TEXT,
                areas_mejora TEXT,
                fortalezas TEXT,
                created_at TEXT,
                FOREIGN KEY (empleado_id) REFERENCES rrhh_empleados(id)
            )
        """
        )

        conn.commit()
        conn.close()

    def registrar_empleado(
        self,
        nombre: str,
        apellido: str,
        puesto: str,
        departamento: str,
        salario_base: float,
        telefono: str = "",
        email: str = "",
    ) -> int:
        """Registrar un nuevo empleado."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rrhh_empleados
            (nombre, apellido, puesto, departamento, fecha_contratacion, salario_base, estado, telefono, email, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 'activo', ?, ?, ?)
        """,
            (
                nombre,
                apellido,
                puesto,
                departamento,
                ahora,
                salario_base,
                telefono,
                email,
                ahora,
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def registrar_horario(
        self, empleado_id: int, fecha: str, hora_entrada: str, hora_salida: str
    ) -> int:
        """Registrar horario de un empleado."""
        ahora = datetime.now().isoformat()

        # Calcular horas trabajadas
        entrada = datetime.strptime(hora_entrada, "%H:%M")
        salida = datetime.strptime(hora_salida, "%H:%M")
        horas_trabajadas = (salida - entrada).total_seconds() / 3600

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rrhh_horarios
            (empleado_id, fecha, hora_entrada, hora_salida, horas_trabajadas, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """,
            (empleado_id, fecha, hora_entrada, hora_salida, horas_trabajadas, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def solicitar_vacaciones(
        self, empleado_id: int, fecha_inicio: str, fecha_fin: str, motivo: str = ""
    ) -> int:
        """Solicitar vacaciones."""
        ahora = datetime.now().isoformat()

        # Calcular días solicitados
        inicio = datetime.strptime(fecha_inicio, "%Y-%m-%d")
        fin = datetime.strptime(fecha_fin, "%Y-%m-%d")
        dias_solicitados = (fin - inicio).days + 1

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rrhh_vacaciones
            (empleado_id, fecha_inicio, fecha_fin, dias_solicitados, estado, motivo, created_at)
            VALUES (?, ?, ?, ?, 'pendiente', ?, ?)
        """,
            (empleado_id, fecha_inicio, fecha_fin, dias_solicitados, motivo, ahora),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def aprobar_vacaciones(self, vacation_id: int, aprobado_por: str) -> bool:
        """Aprobar solicitud de vacaciones."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE rrhh_vacaciones
            SET estado = 'aprobada', aprobado_por = ?, fecha_aprobacion = ?
            WHERE id = ?
        """,
            (aprobado_por, ahora, vacation_id),
        )
        result = cursor.rowcount > 0
        conn.commit()
        conn.close()
        return result

    def generar_nomina(
        self,
        empleado_id: int,
        periodo: str,
        horas_extra: float = 0,
        bonificaciones: float = 0,
        deducciones: float = 0,
    ) -> int:
        """Generar nómina para un empleado."""
        ahora = datetime.now().isoformat()

        # Obtener salario base
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT salario_base FROM rrhh_empleados WHERE id = ?", (empleado_id,))
        result = cursor.fetchone()

        if not result:
            conn.close()
            return 0

        salario_base = result[0]

        # Calcular tarifa por hora extra (suponiendo 1.5x)
        tarifa_hora = salario_base / 160  # Asumiendo 160 horas mensuales
        total_horas_extra = horas_extra * tarifa_hora * 1.5

        total = salario_base + total_horas_extra + bonificaciones - deducciones

        cursor.execute(
            """
            INSERT INTO rrhh_nominas
            (empleado_id, periodo, salario_base, horas_extra, bonificaciones, deducciones, total, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                empleado_id,
                periodo,
                salario_base,
                total_horas_extra,
                bonificaciones,
                deducciones,
                total,
                ahora,
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def crear_evaluacion(
        self,
        empleado_id: int,
        evaluador: str,
        puntaje: int,
        comentarios: str = "",
        areas_mejora: str = "",
        fortalezas: str = "",
    ) -> int:
        """Crear evaluación de desempeño."""
        ahora = datetime.now().isoformat()
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO rrhh_evaluaciones
            (empleado_id, fecha_evaluacion, evaluador, puntaje, comentarios, areas_mejora, fortalezas, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                empleado_id,
                ahora.split("T")[0],
                evaluador,
                puntaje,
                comentarios,
                areas_mejora,
                fortalezas,
                ahora,
            ),
        )
        result = cursor.lastrowid
        conn.commit()
        conn.close()
        return result

    def listar_empleados(self, estado: str = None) -> list[dict]:
        """Listar empleados."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT id, nombre, apellido, puesto, departamento, salario_base, estado FROM rrhh_empleados"
        params = []

        if estado:
            query += " WHERE estado = ?"
            params.append(estado)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "nombre": r[1],
                "apellido": r[2],
                "puesto": r[3],
                "departamento": r[4],
                "salario_base": r[5],
                "estado": r[6],
            }
            for r in rows
        ]

    def vacaciones_pendientes(self) -> list[dict]:
        """Listar vacaciones pendientes de aprobación."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT v.id, e.nombre, e.apellido, v.fecha_inicio, v.fecha_fin, v.dias_solicitados, v.motivo
            FROM rrhh_vacaciones v
            JOIN rrhh_empleados e ON v.empleado_id = e.id
            WHERE v.estado = 'pendiente'
            ORDER BY v.fecha_inicio ASC
        """
        )
        rows = cursor.fetchall()
        conn.close()

        return [
            {
                "id": r[0],
                "empleado": f"{r[1]} {r[2]}",
                "fecha_inicio": r[3],
                "fecha_fin": r[4],
                "dias": r[5],
                "motivo": r[6],
            }
            for r in rows
        ]

    def resumen_rrhh(self) -> dict:
        """Resumen de RRHH."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Total empleados activos
        cursor.execute("SELECT COUNT(*) FROM rrhh_empleados WHERE estado = 'activo'")
        empleados_activos = cursor.fetchone()[0]

        # Vacaciones pendientes
        cursor.execute("SELECT COUNT(*) FROM rrhh_vacaciones WHERE estado = 'pendiente'")
        vacaciones_pendientes = cursor.fetchone()[0]

        # Nominas pendientes de pago
        cursor.execute("SELECT COUNT(*) FROM rrhh_nominas WHERE pagado = 0")
        nominas_pendientes = cursor.fetchone()[0]

        conn.close()

        return {
            "empleados_activos": empleados_activos,
            "vacaciones_pendientes": vacaciones_pendientes,
            "nominas_pendientes": nominas_pendientes,
        }

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteRRHH."""
        texto.lower()
        return "Puedo gestionar empleados, horarios, vacaciones y nóminas. ¿Qué tarea de RRHH necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteRRHH."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteRRHH."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteRRHH."""
        return self.procesar(texto)


if __name__ == "__main__":
    agente = AgenteRRHH()

    # Test: registrar empleado
    empleado_id = agente.registrar_empleado(
        nombre="Juan",
        apellido="García",
        puesto="Camarero",
        departamento="Salón",
        salario_base=1500.0,
        telefono="600123456",
        email="juan@ejemplo.com",
    )
    print(f"Empleado registrado: {empleado_id}")

    # Test: registrar horario
    horario_id = agente.registrar_horario(
        empleado_id=empleado_id,
        fecha=datetime.now().strftime("%Y-%m-%d"),
        hora_entrada="09:00",
        hora_salida="17:00",
    )
    print(f"Horario registrado: {horario_id}")

    # Test: solicitar vacaciones
    vacaciones_id = agente.solicitar_vacaciones(
        empleado_id=empleado_id,
        fecha_inicio="2024-06-01",
        fecha_fin="2024-06-05",
        motivo="Vacaciones familiares",
    )
    print(f"Vacaciones solicitadas: {vacaciones_id}")

    # Test: generar nómina
    nomina_id = agente.generar_nomina(
        empleado_id=empleado_id,
        periodo="2024-05",
        horas_extra=10,
        bonificaciones=100,
        deducciones=50,
    )
    print(f"Nómina generada: {nomina_id}")

    # Test: crear evaluación
    evaluacion_id = agente.crear_evaluacion(
        empleado_id=empleado_id,
        evaluador="Gerente",
        puntaje=85,
        comentarios="Buen desempeño general",
        areas_mejora="Puntualidad",
        fortalezas="Atención al cliente",
    )
    print(f"Evaluación creada: {evaluacion_id}")

    # Test: resumen
    resumen = agente.resumen_rrhh()
    print(f"Resumen RRHH: {resumen}")
