#!/usr/bin/env python3
"""
Agente Administrativo y Contable para Bar - URA System
Gestiona OCR de facturas, control de costes y RRHH
"""

import json
import re
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import cv2
import easyocr

sys.path.append("..")
import contextlib

from utils.agent_base_stability import AgentStabilityBase, cross_check_validator


class AgenteAdministrativoContable(AgentStabilityBase):
    """Agente especializado en administración y contabilidad"""

    def __init__(self):
        super().__init__("agente_administrativo_contable")
        self.facturas_dir = Path("documents/facturas")
        self.albaranes_dir = Path("documents/albaranes")
        self.rrhh_dir = Path("documents/rrhh")
        self.db_path = Path("data/administracion/contabilidad.db")

        # Crear directorios
        self.facturas_dir.mkdir(parents=True, exist_ok=True)
        self.albaranes_dir.mkdir(parents=True, exist_ok=True)
        self.rrhh_dir.mkdir(parents=True, exist_ok=True)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # Inicializar base de datos
        self._init_database()

        # Configuración OCR
        self.reader = easyocr.Reader(["es", "en"])

        # Cargar datos existentes
        self.proveedores = self._load_proveedores()
        self.costes_historicos = self._load_costes_historicos()

    def procesar(self, texto: str) -> str:
        """Procesar consulta sobre administración y contabilidad."""
        texto_lower = texto.lower()

        if "factura" in texto_lower or "ocr" in texto_lower:
            return "Puedo procesar facturas y albaranes mediante OCR. Coloca los archivos en documents/facturas/"

        if "coste" in texto_lower or "proveedor" in texto_lower:
            return (
                "Puedo controlar costes de proveedores y generar informes de variación de precios"
            )

        if "rrhh" in texto_lower or "fichaje" in texto_lower:
            return "Puedo gestionar RRHH y fichajes de empleados"

        if "informe" in texto_lower or "contable" in texto_lower:
            return "Puedo generar informes contables mensuales y anuales"

        return "Agente administrativo y contable disponible. Funciones: OCR de facturas, control de costes, RRHH, informes contables"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción específica sobre administración y contabilidad."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información sobre administración y contabilidad."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder consulta delegando en procesar()."""
        return self.procesar(texto)

    def get_agent_capabilities(self) -> dict[str, Any]:
        """Devuelve las capacidades del agente"""
        return {
            "procesar_factura_ocr": {
                "descripcion": "Procesar factura usando OCR",
                "parametros": ["ruta_imagen"],
                "retorno": "Dict[str, Any]",
            },
            "controlar_costes_proveedores": {
                "descripcion": "Controlar costes y detectar subidas",
                "parametros": ["dias_analisis"],
                "retorno": "Dict[str, Any]",
            },
            "gestionar_rrhh_fichajes": {
                "descripcion": "Gestionar sistema de RRHH",
                "parametros": [],
                "retorno": "Dict[str, Any]",
            },
            "generar_informe_contable": {
                "descripcion": "Generar informe contable",
                "parametros": ["mes", "año"],
                "retorno": "Dict[str, Any]",
            },
        }

    def _init_database(self):
        """Inicializar base de datos contable"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tabla de facturas
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS facturas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_factura TEXT NOT NULL,
                proveedor TEXT NOT NULL,
                fecha_emision DATE,
                fecha_vencimiento DATE,
                importe_total REAL,
                iva REAL,
                base_imponible REAL,
                concepto TEXT,
                estado TEXT DEFAULT 'pendiente',
                ruta_imagen TEXT,
                fecha_procesamiento REAL,
                datos_ocr TEXT
            )
        """
        )

        # Tabla de albaranes
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS albaranes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_albaran TEXT NOT NULL,
                proveedor TEXT NOT NULL,
                fecha DATE,
                productos TEXT,
                importe_total REAL,
                ruta_imagen TEXT,
                fecha_procesamiento REAL,
                datos_ocr TEXT
            )
        """
        )

        # Tabla de proveedores
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS proveedores (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL UNIQUE,
                cif TEXT,
                direccion TEXT,
                telefono TEXT,
                email TEXT,
                categoria TEXT,
                precio_medio_historico REAL,
                ultima_actualizacion REAL
            )
        """
        )

        # Tabla de control de costes
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS control_costes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                producto TEXT NOT NULL,
                proveedor TEXT NOT NULL,
                fecha DATE,
                precio_unitario REAL,
                cantidad REAL,
                precio_total REAL,
                variacion_porcentual REAL,
                alerta_subida INTEGER DEFAULT 0
            )
        """
        )

        # Tabla de RRHH
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS empleados (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                apellidos TEXT,
                dni TEXT UNIQUE,
                puesto TEXT NOT NULL,
                fecha_contratacion DATE,
                salario_base REAL,
                horario_semanal INTEGER,
                email TEXT,
                telefono TEXT,
                estado TEXT DEFAULT 'activo'
            )
        """
        )

        # Tabla de fichajes
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS fichajes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                empleado_id INTEGER,
                fecha DATE,
                hora_entrada TIME,
                hora_salida TIME,
                horas_trabajadas REAL,
                tipo_jornada TEXT,
                observaciones TEXT,
                FOREIGN KEY (empleado_id) REFERENCES empleados (id)
            )
        """
        )

        conn.commit()
        conn.close()

    def _procesar_factura_ocr_core(self, ruta_imagen: str) -> dict[str, Any]:
        """Método core para procesar factura usando OCR y extraer datos"""
        self.log_reasoning_step("OCR_PROCESSING_START", {"ruta_imagen": ruta_imagen})

        try:
            # Validar ruta de imagen
            if not Path(ruta_imagen).exists():
                raise FileNotFoundError(f"Archivo no encontrado: {ruta_imagen}")

            # Cargar imagen
            imagen = cv2.imread(ruta_imagen)
            if imagen is None:
                raise ValueError("No se pudo cargar la imagen")

            # Validar dimensiones
            if imagen.shape[0] < 100 or imagen.shape[1] < 100:
                raise ValueError("Imagen demasiado pequeña para procesar")

            # Preprocesamiento
            gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
            _, binaria = cv2.threshold(gris, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

            # OCR con EasyOCR
            resultados = self.reader.readtext(binaria)

            # Validar resultados OCR
            if len(resultados) == 0:
                raise ValueError("No se detectó texto en la imagen")

            # Extraer texto
            texto_completo = " ".join([texto for (_, texto, _) in resultados])

            # Validar texto extraído
            if len(texto_completo.strip()) < 10:
                raise ValueError("Texto extraído demasiado corto")

            # Extraer datos estructurados
            datos_factura = self._extraer_datos_factura(texto_completo, resultados)

            # Validación matemática de datos financieros
            validation_result = cross_check_validator.mathematical_cross_check(
                datos_factura, "factura_ocr_validation"
            )

            if not validation_result["is_valid"]:
                self.log_reasoning_step("MATHEMATICAL_VALIDATION_FAILED", validation_result, 0.3)
                # No bloquear, pero registrar advertencia
                datos_factura["validation_warnings"] = validation_result["issues"]

            # Guardar en base de datos
            factura_id = self._guardar_factura(datos_factura, ruta_imagen)

            confianza_ocr = self._calcular_confianza_ocr(resultados)

            self.log_reasoning_step(
                "OCR_PROCESSING_COMPLETE",
                {
                    "factura_id": factura_id,
                    "confianza_ocr": confianza_ocr,
                    "validation_passed": validation_result["is_valid"],
                },
                confianza_ocr,
            )

            return {
                "factura_id": factura_id,
                "datos_extraidos": datos_factura,
                "texto_completo": texto_completo,
                "confianza_ocr": confianza_ocr,
                "validation": validation_result,
            }

        except Exception as e:
            self.log_reasoning_step("OCR_PROCESSING_ERROR", {"error": str(e)}, 0.0)
            raise

    def procesar_factura_ocr(self, ruta_imagen: str) -> dict[str, Any]:
        """Procesar factura usando OCR con control de estabilidad"""
        return self.process_with_stability_control("_procesar_factura_ocr_core", ruta_imagen)

    def _extraer_datos_factura(self, texto: str, resultados_ocr: list) -> dict[str, Any]:
        """Extraer datos estructurados de factura usando patrones"""
        datos = {
            "numero_factura": None,
            "proveedor": None,
            "fecha_emision": None,
            "fecha_vencimiento": None,
            "importe_total": None,
            "iva": None,
            "base_imponible": None,
            "concepto": [],
        }

        # Patrones de búsqueda
        patrones = {
            "numero_factura": [
                r"(?:FACTURA|N[º°]\s*)(\d+[-/]?\d*)",
                r"INVOICE\s*(\d+[-/]?\d*)",
                r"N[º°]\s*FACTURA[:\s]*(\d+[-/]?\d*)",
            ],
            "fecha": [
                r"(\d{2}[-/]\d{2}[-/]\d{4})",
                r"(\d{1,2}\sde\s\w+\sde\s\d{4})",
                r"Fecha[:\s]*(\d{2}[-/]\d{2}[-/]\d{4})",
            ],
            "importe_total": [
                r"TOTAL[:\s]*[\$]?\s*(\d+[.,]\d{2})",
                r"IMPORTE[:\s]*[\$]?\s*(\d+[.,]\d{2})",
                r"EUROS?[:\s]*(\d+[.,]\d{2})\s*?",
            ],
            "iva": [r"IVA[:\s]*(\d+[.,]\d{2})%", r"VAT[:\s]*(\d+[.,]\d{2})%"],
            "base_imponible": [
                r"BASE\s*IMPNIBLE[:\s]*(\d+[.,]\d{2})",
                r"SUBTOTAL[:\s]*(\d+[.,]\d{2})",
            ],
        }

        # Buscar patrones
        for campo, lista_patrones in patrones.items():
            for patron in lista_patrones:
                coincidencias = re.findall(patron, texto, re.IGNORECASE)
                if coincidencias:
                    if campo == "fecha":
                        datos["fecha_emision"] = coincidencias[0]
                    elif campo == "importe_total":
                        # Limpiar y convertir número
                        importe_str = coincidencias[0].replace(",", ".")
                        with contextlib.suppress(ValueError):
                            datos[campo] = float(importe_str)
                    elif campo == "iva" or campo == "base_imponible":
                        importe_str = coincidencias[0].replace(",", ".")
                        with contextlib.suppress(ValueError):
                            datos[campo] = float(importe_str)
                    else:
                        datos[campo] = coincidencias[0]
                    break

        # Detectar proveedor (buscar en líneas con alta confianza)
        for _, texto, confianza in resultados_ocr:
            if confianza > 0.8 and len(texto) > 3:
                # Palabras clave de proveedores
                if any(
                    palabra in texto.upper()
                    for palabra in ["DISTRIBUIDORA", "PROVEEDOR", "S.L.", "SA", "IMPORT"]
                ):
                    datos["proveedor"] = texto
                    break

        # Extraer conceptos (líneas con productos)
        lineas_productos = []
        for _bbox, texto, confianza in resultados_ocr:
            if confianza > 0.7 and any(char.isdigit() for char in texto):
                # Posible línea de producto
                if re.search(r"\d+[.,]\d{2}", texto):
                    lineas_productos.append(texto)

        datos["concepto"] = lineas_productos

        return datos

    def _calcular_confianza_ocr(self, resultados: list) -> float:
        """Calcular confianza promedio del OCR"""
        if not resultados:
            return 0.0

        confianzas = [confianza for _, _, confianza in resultados]
        return sum(confianzas) / len(confianzas)

    def _guardar_factura(self, datos: dict[str, Any], ruta_imagen: str) -> int:
        """Guardar factura en base de datos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO facturas
            (numero_factura, proveedor, fecha_emision, fecha_vencimiento,
             importe_total, iva, base_imponible, concepto, ruta_imagen,
             fecha_procesamiento, datos_ocr)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datos.get("numero_factura"),
                datos.get("proveedor"),
                datos.get("fecha_emision"),
                datos.get("fecha_vencimiento"),
                datos.get("importe_total"),
                datos.get("iva"),
                datos.get("base_imponible"),
                json.dumps(datos.get("concepto", [])),
                ruta_imagen,
                time.time(),
                json.dumps(datos),
            ),
        )

        factura_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return factura_id

    def controlar_costes_proveedores(self, dias_analisis: int = 30) -> dict[str, Any]:
        """Controlar costes y detectar subidas de precios"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Obtener costes recientes
        fecha_limite = datetime.now() - timedelta(days=dias_analisis)

        cursor.execute(
            """
            SELECT producto, proveedor, AVG(precio_unitario) as precio_promedio,
                   COUNT(*) as transacciones
            FROM control_costes
            WHERE fecha > ?
            GROUP BY producto, proveedor
            ORDER BY producto, proveedor
        """,
            (fecha_limite.strftime("%Y-%m-%d"),),
        )

        costes_actuales = cursor.fetchall()

        # Comparar con históricos
        alertas_subida = []
        analisis_costes = []

        for producto, proveedor, precio_actual, transacciones in costes_actuales:
            # Buscar precio histórico
            precio_historico = self._get_precio_historico(producto, proveedor)

            if precio_historico and precio_historico > 0:
                variacion = ((precio_actual - precio_historico) / precio_historico) * 100

                if variacion > 10:  # Alerta si sube más del 10%
                    alertas_subida.append(
                        {
                            "producto": producto,
                            "proveedor": proveedor,
                            "precio_actual": precio_actual,
                            "precio_historico": precio_historico,
                            "variacion_porcentual": round(variacion, 2),
                            "gravedad": "Alta" if variacion > 20 else "Media",
                        }
                    )

                # Actualizar control de costes
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO control_costes
                    (producto, proveedor, fecha, precio_unitario, variacion_porcentual, alerta_subida)
                    VALUES (?, ?, ?, ?, ?, ?)
                """,
                    (
                        producto,
                        proveedor,
                        datetime.now().strftime("%Y-%m-%d"),
                        precio_actual,
                        variacion,
                        1 if variacion > 10 else 0,
                    ),
                )

            analisis_costes.append(
                {
                    "producto": producto,
                    "proveedor": proveedor,
                    "precio_actual": precio_actual,
                    "precio_historico": precio_historico,
                    "variacion": (
                        round(((precio_actual - precio_historico) / precio_historico * 100), 2)
                        if precio_historico
                        else 0
                    ),
                    "transacciones": transacciones,
                }
            )

        conn.commit()
        conn.close()

        return {
            "periodo_analizado": f"Últimos {dias_analisis} días",
            "total_productos": len(analisis_costes),
            "alertas_subida": len(alertas_subida),
            "alertas_detalle": alertas_subida,
            "analisis_completo": analisis_costes,
        }

    def _get_precio_historico(self, producto: str, proveedor: str) -> float | None:
        """Obtener precio histórico de producto"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT AVG(precio_unitario)
            FROM control_costes
            WHERE producto = ? AND proveedor = ?
            AND fecha < date('now', '-30 days')
        """,
            (producto, proveedor),
        )

        resultado = cursor.fetchone()
        conn.close()

        return resultado[0] if resultado else None

    def gestionar_rrhh_fichajes(self) -> dict[str, Any]:
        """Gestionar sistema de RRHH y fichajes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Obtener empleados activos
        cursor.execute('SELECT * FROM empleados WHERE estado = "activo"')
        empleados = cursor.fetchall()

        # Obtener fichajes de la semana
        semana_actual = datetime.now().isocalendar()[1]
        cursor.execute(
            """
            SELECT e.nombre, e.apellidos, f.fecha, f.hora_entrada, f.hora_salida, f.horas_trabajadas
            FROM fichajes f
            JOIN empleados e ON f.empleado_id = e.id
            WHERE strftime('%W', f.fecha) = ?
            ORDER BY f.fecha, f.hora_entrada
        """,
            (str(semana_actual),),
        )

        fichajes_semana = cursor.fetchall()

        # Calcular estadísticas
        total_horas_semana = sum(ficha[5] for ficha in fichajes_semana if ficha[5])
        empleados_activos = len(empleados)

        # Detectar anomalías
        anomalías = []
        for ficha in fichajes_semana:
            if ficha[5] and ficha[5] > 10:  # Más de 10 horas en un día
                anomalías.append(
                    {
                        "empleado": f"{ficha[0]} {ficha[1]}",
                        "fecha": ficha[2],
                        "horas_trabajadas": ficha[5],
                        "tipo": "Horas excesivas",
                    }
                )
            elif ficha[3] and not ficha[4]:  # Entrada sin salida
                anomalías.append(
                    {
                        "empleado": f"{ficha[0]} {ficha[1]}",
                        "fecha": ficha[2],
                        "entrada": ficha[3],
                        "tipo": "Falta registro de salida",
                    }
                )

        conn.close()

        return {
            "empleados_activos": empleados_activos,
            "fichajes_semana": len(fichajes_semana),
            "total_horas_semana": total_horas_semana,
            "horas_promedio_empleado": total_horas_semana / max(1, empleados_activos),
            "anomalias_detectadas": len(anomalías),
            "detalle_anomalias": anomalías,
        }

    def registrar_empleado(self, datos_empleado: dict[str, Any]) -> int:
        """Registrar nuevo empleado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO empleados
            (nombre, apellidos, dni, puesto, fecha_contratacion, salario_base,
             horario_semanal, email, telefono)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                datos_empleado["nombre"],
                datos_empleado.get("apellidos", ""),
                datos_empleado.get("dni", ""),
                datos_empleado["puesto"],
                datos_empleado.get("fecha_contratacion", datetime.now().strftime("%Y-%m-%d")),
                datos_empleado.get("salario_base", 0),
                datos_empleado.get("horario_semanal", 40),
                datos_empleado.get("email", ""),
                datos_empleado.get("telefono", ""),
            ),
        )

        empleado_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return empleado_id

    def registrar_fichaje(self, empleado_id: int, tipo: str = "entrada") -> bool:
        """Registrar fichaje de empleado"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        fecha_actual = datetime.now().strftime("%Y-%m-%d")
        hora_actual = datetime.now().strftime("%H:%M:%S")

        if tipo == "entrada":
            # Buscar si ya hay entrada hoy
            cursor.execute(
                """
                SELECT id FROM fichajes
                WHERE empleado_id = ? AND fecha = ? AND hora_entrada IS NOT NULL
            """,
                (empleado_id, fecha_actual),
            )

            if cursor.fetchone():
                conn.close()
                return False  # Ya fichó entrada hoy

            cursor.execute(
                """
                INSERT INTO fichajes (empleado_id, fecha, hora_entrada, tipo_jornada)
                VALUES (?, ?, ?, ?)
            """,
                (empleado_id, fecha_actual, hora_actual, "normal"),
            )

        elif tipo == "salida":
            # Buscar fichaje de entrada sin salida
            cursor.execute(
                """
                SELECT id, hora_entrada FROM fichajes
                WHERE empleado_id = ? AND fecha = ? AND hora_salida IS NULL
            """,
                (empleado_id, fecha_actual),
            )

            resultado = cursor.fetchone()
            if not resultado:
                conn.close()
                return False  # No hay entrada registrada

            # Calcular horas trabajadas
            hora_entrada = resultado[1]
            try:
                entrada_dt = datetime.strptime(
                    f"{fecha_actual} {hora_entrada}", "%Y-%m-%d %H:%M:%S"
                )
                salida_dt = datetime.strptime(f"{fecha_actual} {hora_actual}", "%Y-%m-%d %H:%M:%S")
                horas_trabajadas = (salida_dt - entrada_dt).total_seconds() / 3600

                cursor.execute(
                    """
                    UPDATE fichajes
                    SET hora_salida = ?, horas_trabajadas = ?
                    WHERE id = ?
                """,
                    (hora_actual, round(horas_trabajadas, 2), resultado[0]),
                )

            except ValueError:
                conn.close()
                return False

        conn.commit()
        conn.close()
        return True

    def generar_informe_contable(self, mes: int = None, año: int = None) -> dict[str, Any]:
        """Generar informe contable mensual"""
        if mes is None:
            mes = datetime.now().month
        if año is None:
            año = datetime.now().year

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Facturas del mes
        cursor.execute(
            """
            SELECT COUNT(*) as total, SUM(importe_total) as importe_total,
                   SUM(base_imponible) as base_total, SUM(iva) as iva_total
            FROM facturas
            WHERE strftime('%m', fecha_procesamiento) = ?
            AND strftime('%Y', fecha_procesamiento) = ?
        """,
            (f"{mes:02d}", str(año)),
        )

        resultado_facturas = cursor.fetchone()

        # Top proveedores del mes
        cursor.execute(
            """
            SELECT proveedor, COUNT(*) as num_facturas, SUM(importe_total) as total_importe
            FROM facturas
            WHERE strftime('%m', fecha_procesamiento) = ?
            AND strftime('%Y', fecha_procesamiento) = ?
            GROUP BY proveedor
            ORDER BY total_importe DESC
            LIMIT 10
        """,
            (f"{mes:02d}", str(año)),
        )

        top_proveedores = cursor.fetchall()

        # Costes por categoría
        cursor.execute(
            """
            SELECT concepto, COUNT(*) as frecuencia
            FROM facturas
            WHERE strftime('%m', fecha_procesamiento) = ?
            AND strftime('%Y', fecha_procesamiento) = ?
            GROUP BY concepto
        """,
            (f"{mes:02d}", str(año)),
        )

        costes_categoria = cursor.fetchall()

        conn.close()

        return {
            "periodo": f"{mes:02d}/{año}",
            "resumen_facturas": {
                "total_facturas": resultado_facturas[0] or 0,
                "importe_total": resultado_facturas[1] or 0,
                "base_imponible": resultado_facturas[2] or 0,
                "iva_total": resultado_facturas[3] or 0,
            },
            "top_proveedores": [
                {"proveedor": row[0], "facturas": row[1], "importe": row[2]}
                for row in top_proveedores
            ],
            "costes_categoria": [
                {"categoria": row[0], "frecuencia": row[1]} for row in costes_categoria
            ],
        }

    def _load_proveedores(self) -> list[dict]:
        """Cargar proveedores existentes"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM proveedores")
        proveedores = cursor.fetchall()

        conn.close()

        return [
            {
                "id": row[0],
                "nombre": row[1],
                "cif": row[2],
                "direccion": row[3],
                "telefono": row[4],
                "email": row[5],
                "categoria": row[6],
                "precio_medio": row[7],
            }
            for row in proveedores
        ]

    def _load_costes_historicos(self) -> list[dict]:
        """Cargar costes históricos"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM control_costes ORDER BY fecha DESC LIMIT 100")
        costes = cursor.fetchall()

        conn.close()

        return [
            {
                "producto": row[1],
                "proveedor": row[2],
                "fecha": row[3],
                "precio_unitario": row[4],
                "variacion": row[6],
            }
            for row in costes
        ]

        """Responder pregunta sobre administración y contabilidad."""
        return self.procesar(texto)


# Instancia global
agente_administrativo_contable = AgenteAdministrativoContable()

if __name__ == "__main__":
    # Ejemplo de uso
    agente = AgenteAdministrativoContable()

    # Procesar factura de ejemplo
    print("Agente Administrativo y Contable inicializado")
    print("Funciones disponibles:")
    print("- OCR de facturas y albaranes")
    print("- Control de costes de proveedores")
    print("- Gestión de RRHH y fichajes")
    print("- Informes contables")

    # Generar informe del mes actual
    informe = agente.generar_informe_contable()
    print(f"Informe contable: {informe['periodo']}")
