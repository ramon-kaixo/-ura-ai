"""
AGENTE VERIFICADOR INSTALACIONES - Verifica que TODO está bien instalado y supervisado
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

GRUPOS_SUPERVISION = {
    "CORE": {
        "agentes": ["arquitectura", "programador", "revisor", "sistemas", "instalador"],
        "supervision": ["estado_codigo", "errores", "integraciones"],
        "seguridad": ["permisos", "accesos"],
        "periodicidad": "1 hora",
    },
    "SUPERVISION": {
        "agentes": ["auditor", "supervisor", "lenguaje"],
        "supervision": ["registros_activos", "alertas_generadas"],
        "seguridad": ["logs_auditoria", "integridad"],
        "periodicidad": "30 min",
    },
    "EXTERNO": {
        "agentes": ["auditor_externo", "ia_externa"],
        "supervision": ["conectividad", "respuestas"],
        "seguridad": ["credenciales", "apis"],
        "periodicidad": "15 min",
    },
    "COCINA": {
        "agentes": [
            "cocina_espanola",
            "cocina_italiana",
            "cocina_peruana",
            "cocina_mexicana",
            "vocabulario_gastronomico",
        ],
        "supervision": ["datos_actualizados", "fotos_disponibles"],
        "seguridad": [],
        "periodicidad": "1 día",
    },
    "BIBLIOTECA": {
        "agentes": [
            "biblioteca",
            "documentos_word",
            "documentos_excel",
            "documentos_pdf",
            "vocabulario_*",
        ],
        "supervision": ["indice_completo", "busquedas_funcionan"],
        "seguridad": ["permisos_archivos"],
        "periodicidad": "1 día",
    },
    "AUTONOMIA": {
        "agentes": ["autonomia_loop"],
        "supervision": [
            "loop_activo",
            "detecciones_pendientes",
            "instalaciones_completadas",
            "logs_sin_errores",
        ],
        "seguridad": ["apps_sospechosas"],
        "periodicidad": "5 min",
    },
    "NEGOCIO": {
        "agentes": ["contabilidad", "banco", "laboral", "marketing", "email"],
        "supervision": ["datos_al_dia", "facturas_procesadas"],
        "seguridad": ["datos_fiscales", "backup_datos"],
        "periodicidad": "1 día",
    },
}


def verificar_grupo(grupo):
    """Verifica un grupo completo"""
    resultados = {
        "grupo": grupo,
        "agentes_esperados": 0,
        "agentes_instalados": 0,
        "supervision": {},
        "problemas": [],
    }

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Obtener agentes esperados de la matriz de supervision
    c.execute("SELECT COUNT(*) FROM supervision_matrix WHERE grupo = ?", (grupo,))
    resultados["agentes_esperados"] = c.fetchone()[0]

    # Obtener agentes instalados de ese grupo
    c.execute(
        "SELECT COUNT(*) FROM agentes_instalados WHERE grupo = ? AND estado = 'activo'", (grupo,)
    )
    resultados["agentes_instalados"] = c.fetchone()[0]

    # Verificar ultimo check de cada agente
    c.execute(
        """
        SELECT agente, ultimo_check, estado
        FROM supervision_matrix
        WHERE grupo = ?
    """,
        (grupo,),
    )

    for agente, ultimo_check, estado in c.fetchall():
        resultados["supervision"][agente] = {"ultimo_check": ultimo_check, "estado": estado}

        # Verificar si necesita atencion
        if estado != "OK":
            resultados["problemas"].append(f"{agente}: {estado}")

    # Verificaciones especificas por grupo
    if grupo == "AUTONOMIA":
        import subprocess

        result = subprocess.run(["pgrep", "-f", "autonomia_loop"], capture_output=True)
        if result.returncode != 0:
            resultados["problemas"].append("autonomia_loop: NO ACTIVO")
        else:
            resultados["supervision"]["autonomia_loop"] = {"ultimo_check": "AHORA", "estado": "OK"}

    conn.close()

    resultados["estado"] = "OK" if not resultados["problemas"] else "PROBLEMAS"

    return resultados


def verificar_supervision(tipo, grupo):
    """Verifica un tipo específico de supervisión"""
    if tipo == "loop_activo":
        import subprocess

        result = subprocess.run(["pgrep", "-f", "autonomia_loop"], capture_output=True)
        return "OK" if result.returncode == 0 else "PARADO"

    elif tipo == "detecciones_pendientes":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM apps_pendientes WHERE estado='pendiente'")
        count = c.fetchone()[0]
        conn.close()
        return f"{count} pendientes"

    elif tipo == "logs_sin_errores":
        log_path = Path(__file__).parent.parent / "logs" / "autonomy.log"
        if log_path.exists():
            with open(log_path) as f:
                contenido = f.read()
                if "ERROR" in contenido or "FALLO" in contenido:
                    return "CON ERRORES"
        return "OK"

    elif tipo == "registros_activos":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        try:
            c.execute("SELECT COUNT(*) FROM auditoria")
            count = c.fetchone()[0]
            conn.close()
            return f"{count} registros"
        except:
            conn.close()
            return "SIN DATOS"

    elif tipo == "conectividad":
        try:
            import urllib.request

            urllib.request.urlopen("https://api.github.com", timeout=5)  # nosec B310
            return "OK"
        except:
            return "SIN CONEXION"

    return "OK"


def verificacion_completa():
    """Verifica TODOS los grupos"""
    resultados = {
        "timestamp": datetime.now().isoformat(),
        "grupos": {},
        "resumen": {"total_grupos": len(GRUPOS_SUPERVISION), "ok": 0, "problemas": 0},
    }

    for grupo in GRUPOS_SUPERVISION:
        resultado = verificar_grupo(grupo)
        resultados["grupos"][grupo] = resultado

        if resultado.get("estado") == "OK":
            resultados["resumen"]["ok"] += 1
        else:
            resultados["resumen"]["problemas"] += 1

    # Guardar en BD
    guardar_verificacion(resultados)

    return resultados


def guardar_verificacion(resultados):
    """Guarda resultado de verificación"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS verificaciones_instalacion (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            grupos_ok INTEGER,
            grupos_problemas INTEGER,
            detalles TEXT
        )
    """)

    c.execute(
        """
        INSERT INTO verificaciones_instalacion
        (timestamp, grupos_ok, grupos_problemas, detalles)
        VALUES (?, ?, ?, ?)
    """,
        (
            resultados["timestamp"],
            resultados["resumen"]["ok"],
            resultados["resumen"]["problemas"],
            str(resultados["grupos"]),
        ),
    )

    conn.commit()
    conn.close()


def agentes_sin_supervisar():
    """Lista agentes que no están en ningún grupo supervisado"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Obtener todos los agentes instalados
    c.execute("SELECT nombre FROM agentes_instalados WHERE estado='activo'")
    instalados = {r[0] for r in c.fetchall()}

    # Obtener agentes supervisados
    supervisados = set()
    for _grupo, config in GRUPOS_SUPERVISION.items():
        supervisados.update(config["agentes"])

    # Encontrar los no supervisados
    sin_supervisar = instalados - supervisados

    conn.close()

    return list(sin_supervisar)


def generar_informe_verificacion():
    """Genera informe de verificación completo"""
    verificacion = verificacion_completa()
    sin_supervisar = agentes_sin_supervisar()

    informe = f"""# INFORME DE VERIFICACIÓN URA
## Fecha: {verificacion["timestamp"][:10]}

## Resumen
- Grupos verificados: {verificacion["resumen"]["total_grupos"]}
- OK: {verificacion["resumen"]["ok"]}
- Problemas: {verificacion["resumen"]["problemas"]}

## Estado por Grupo
"""

    for grupo, resultado in verificacion["grupos"].items():
        estado = resultado.get("estado", "DESCONOCIDO")
        emoji = "✅" if estado == "OK" else "⚠️"

        informe += f"""
### {emoji} {grupo}
- Estado: {estado}
- Agentes: {resultado.get("agentes_instalados", 0)}/{resultado.get("agentes_esperados", 0)}
- Supervisión: {list(resultado.get("supervision", {}).values())}
"""

        if resultado.get("problemas"):
            informe += f"- ⚠️ Problemas: {resultado['problemas']}\n"

    if sin_supervisar:
        informe += f"""
## Agentes sin supervisar
{", ".join(sin_supervisar)}
"""
    else:
        informe += """
## Agentes sin supervisar
Ninguno - todos supervisados ✅
"""

    return informe


if __name__ == "__main__":
    print("=== VERIFICADOR DE INSTALACIONES ===")
    verificacion = verificacion_completa()

    print(f"\n📊 Grupos: {verificacion['resumen']['total_grupos']}")
    print(f"   OK: {verificacion['resumen']['ok']}")
    print(f"   Problemas: {verificacion['resumen']['problemas']}")

    print("\n📋 Estado por grupo:")
    for grupo, resultado in verificacion["grupos"].items():
        emoji = "✅" if resultado.get("estado") == "OK" else "⚠️"
        print(f"   {emoji} {grupo}: {resultado.get('estado')}")

    sin_sup = agentes_sin_supervisar()
    if sin_sup:
        print(f"\n⚠️ Sin supervisar: {sin_sup}")
    else:
        print("\n✅ Todos los agentes están supervisados")
