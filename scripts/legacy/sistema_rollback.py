#!/usr/bin/env python3
"""
Sistema de Rollback Automático URA
Rollback automático basado en trazabilidad del archivist
"""

import sqlite3
import subprocess
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"
CODE_DIR = Path(__file__).parent.parent / "core"


class SistemaRollback:
    """Sistema de rollback automático"""

    def __init__(self):
        self.db_path = DB_PATH
        self.code_dir = CODE_DIR

    def obtener_ultima_version_aprobada(self, archivo: str) -> dict | None:
        """Obtiene la última versión aprobada de un archivo"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            SELECT hash_despues, timestamp
            FROM cambios_codigo
            WHERE archivo = ? AND estado = 'aprobado'
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (archivo,),
        )

        row = c.fetchone()
        conn.close()

        if not row:
            return None

        return {"hash": row[0], "timestamp": row[1]}

    def verificar_integridad_actual(self, archivo: str) -> bool:
        """Verifica si el archivo actual coincide con la última versión aprobada"""
        import hashlib

        archivo_path = Path(archivo)
        if not archivo_path.exists():
            return False

        with open(archivo_path, "rb") as f:
            hash_actual = hashlib.sha256(f.read()).hexdigest()

        ultima_aprobada = self.obtener_ultima_version_aprobada(archivo)
        if not ultima_aprobada:
            return True  # Sin historia, asumir OK

        return hash_actual == ultima_aprobada["hash"]

    def detectar_problemas_post_cambio(self, archivo: str) -> bool:
        """Detecta si un cambio causó problemas"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        # Verificar si hay fallos después del cambio
        c.execute(
            """
            SELECT timestamp FROM cambios_codigo
            WHERE archivo = ? AND estado = 'aprobado'
            ORDER BY timestamp DESC
            LIMIT 1
        """,
            (archivo,),
        )

        row = c.fetchone()
        if not row:
            conn.close()
            return False

        timestamp_cambio = row[0]

        # Fallos después del cambio
        c.execute(
            """
            SELECT COUNT(*) FROM metricas_agente
            WHERE exito = FALSE AND timestamp > ?
        """,
            (timestamp_cambio,),
        )
        fallos_post_cambio = c.fetchone()[0]

        conn.close()

        return fallos_post_cambio > 5  # Umbral: 5 fallos después del cambio

    def ejecutar_rollback_git(self, archivo: str, commit_hash: str = None) -> bool:
        """Ejecuta rollback usando Git"""
        archivo_path = Path(archivo)

        try:
            # Si no se especifica commit, usar HEAD~1
            if commit_hash:
                subprocess.run(
                    ["git", "checkout", commit_hash, "--", str(archivo_path)],
                    cwd=self.code_dir,
                    check=True,
                    capture_output=True,
                )
            else:
                subprocess.run(
                    ["git", "checkout", "HEAD~1", "--", str(archivo_path)],
                    cwd=self.code_dir,
                    check=True,
                    capture_output=True,
                )

            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Error en Git rollback: {e}")
            return False

    def registrar_rollback(self, archivo: str, razon: str):
        """Registra un rollback en la base de datos"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()

        c.execute(
            """
            INSERT INTO cambios_codigo
            (timestamp, archivo, cambio_detectado, estado)
            VALUES (?, ?, ?, 'rollback')
        """,
            (datetime.now().isoformat(), archivo, f"ROLLBACK: {razon}"),
        )

        conn.commit()
        conn.close()

    def rollback_automatico(self, archivo: str) -> bool:
        """Ejecuta rollback automático si se detectan problemas"""
        if not self.verificar_integridad_actual(archivo):
            print(f"⚠️ {archivo} no coincide con versión aprobada")

        if self.detectar_problemas_post_cambio(archivo):
            print(f"🔄 Detectados problemas post-cambio en {archivo}")
            print("   Ejecutando rollback automático...")

            if self.ejecutar_rollback_git(archivo):
                self.registrar_rollback(archivo, "Problemas detectados post-cambio")
                print(f"✅ Rollback exitoso para {archivo}")
                return True
            else:
                print(f"❌ Falló rollback para {archivo}")
                return False

        return False

    def verificar_todos_archivos(self) -> dict:
        """Verifica todos los archivos y ejecuta rollback si necesario"""
        resultados = {
            "archivos_verificados": 0,
            "rollbacks_ejecutados": 0,
            "archivos_con_problemas": [],
        }

        for archivo in self.code_dir.glob("*.py"):
            resultados["archivos_verificados"] += 1

            if self.rollback_automatico(str(archivo)):
                resultados["rollbacks_ejecutados"] += 1
                resultados["archivos_con_problemas"].append(str(archivo))

        return resultados


if __name__ == "__main__":
    print("=" * 50)
    print("SISTEMA DE ROLLBACK AUTOMÁTICO")
    print("=" * 50)

    rollback = SistemaRollback()

    print("\n🔍 Verificando todos los archivos...")
    resultados = rollback.verificar_todos_archivos()

    print("\n📊 Resultados:")
    print(f"   Archivos verificados: {resultados['archivos_verificados']}")
    print(f"   Rollbacks ejecutados: {resultados['rollbacks_ejecutados']}")

    if resultados["archivos_con_problemas"]:
        print("\n⚠️ Archivos con problemas:")
        for a in resultados["archivos_con_problemas"]:
            print(f"   - {a}")
    else:
        print("\n✅ No se detectaron problemas")

    print("\n✅ Sistema de rollback OK")
