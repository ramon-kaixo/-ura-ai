"""
AGENTE LENGUAJE TÉCNICO - Vocabulario técnico mejorado
Extiende el vocabulario técnico con más términos y funcionalidades
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from agente_logger import AgenteLogger

logger = AgenteLogger("agente_lenguaje_tecnico")

import sqlite3
from datetime import datetime

DB_PATH = Path(__file__).parent.parent / "board.db"

TERMINOS_AVANZADOS = [
    (
        "REST",
        "Estilo de arquitectura para servicios web, usa métodos HTTP estándar",
        "API RESTful con GET, POST, PUT, DELETE",
        "RESTful, RESTful API",
    ),
    (
        "JWT",
        "Token web JSON - estándar para autenticación stateless",
        "Autenticar con JWT token",
        "token, bearer",
    ),
    (
        "ORM",
        "Mapeo objeto-relacional - biblioteca que convierte BD a objetos",
        "Usar SQLAlchemy como ORM",
        "object-relational mapping",
    ),
    (
        "CRUD",
        "Create, Read, Update, Delete - operaciones básicas de datos",
        "Implementar CRUD completo",
        "operaciones, datos",
    ),
    (
        "CI/CD",
        "Integración y despliegue continuo - automatización de builds y deploys",
        "Pipeline CI/CD con GitHub Actions",
        "pipeline, automatización",
    ),
    (
        "SSL/TLS",
        "Protocolos de cifrado para comunicaciones seguras en internet",
        "Certificado SSL para HTTPS",
        "cifrado, seguridad",
    ),
    (
        "nginx",
        "Servidor web y proxy inverso de alto rendimiento",
        "Configurar nginx como reverse proxy",
        "servidor, proxy",
    ),
    (
        "postgres",
        "Base de datos relacional avanzada, extensión de SQL",
        "Migrar de SQLite a PostgreSQL",
        "PostgreSQL, bd",
    ),
    (
        "redis",
        "Base de datos en memoria, clave-valor ultrarrápida",
        "Usar Redis para caché",
        "caché, memoria",
    ),
    (
        "docker-compose",
        "Herramienta para definir y ejecutar aplicaciones multi-contenedor",
        "docker-compose up -d",
        "multi-container, orquestación",
    ),
    (
        "kubernetes",
        "Orquestador de contenedores en producción",
        "Desplegar cluster con K8s",
        "K8s, orquestación",
    ),
    (
        "git_branch",
        "Línea de desarrollo paralela en Git",
        "Crear branch feature/nueva",
        "rama, fork",
    ),
    (
        "pull_request",
        "Solicitud para fusionar cambios en repositorio",
        "Abrir PR para revisión",
        "PR, merge request",
    ),
    (
        "markdown",
        "Lenguaje de marcado ligero para documentación",
        "Escribir README en markdown",
        "md, markup",
    ),
    (
        "terminal",
        "Interfaz de línea de comandos del sistema",
        "Ejecutar en terminal",
        "CLI, bash, shell",
    ),
    (
        "variable_entorno",
        "Valor dinámico del sistema operativo",
        "export FLASK_ENV=production",
        "env, ENV",
    ),
    (
        "debug",
        "Depuración - proceso de encontrar errores",
        "Activar modo debug",
        "debugging, troubleshooting",
    ),
    (
        "hotfix",
        "Corrección urgente de bug en producción",
        "Deploy hotfix inmediatamente",
        "parche, fix urgente",
    ),
    (
        "refactorizar",
        "Reescribir código sin cambiar funcionalidad",
        "Refactorizar función antigua",
        "reestructurar, mejorar",
    ),
    (
        "deployment",
        "Despliegue - poner aplicación en producción",
        "Deployment a producción",
        "deploy, puesta en marcha",
    ),
    (
        "versionado",
        "Control de versiones del software",
        "Semver: 1.2.3 (major.minor.patch)",
        "semver, versioning",
    ),
    (
        "migración",
        "Cambio estructurado de esquema de BD",
        "Crear migración con Alembic",
        "alterar BD, schema",
    ),
    (
        "framework",
        "Estructura base que acelera desarrollo",
        "Django es un framework web",
        "librería, plataforma",
    ),
    ("API_endpoint", "URL específica de una API", "GET /api/usuarios es endpoint", "ruta, URL"),
    (
        "webhook",
        "Notificación automática a URL cuando ocurre evento",
        "Webhook de Stripe al pagar",
        "callback, notificación",
    ),
]


def init_vocabulario_tecnico_avanzado():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    for termino, definicion, ejemplo, sinonimos in TERMINOS_AVANZADOS:
        c.execute(
            """
            INSERT OR IGNORE INTO biblioteca_vocabulario (categoria, termino, definicion, ejemplo, sinonimos, area, created_at)
            VALUES ('tecnico', ?, ?, ?, ?, 'sistemas', ?)
        """,
            (termino, definicion, ejemplo, sinonimos, datetime.now().isoformat()),
        )

    conn.commit()
    conn.close()


def buscar_termino_tecnico(termino):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT termino, definicion, ejemplo, sinonimos, area
        FROM biblioteca_vocabulario
        WHERE categoria = 'tecnico' AND (
            termino LIKE ? OR
            definicion LIKE ? OR
            sinonimos LIKE ?
        )
    """,
        (f"%{termino}%", f"%{termino}%", f"%{termino}%"),
    )

    resultados = c.fetchall()
    conn.close()

    if resultados:
        return [
            {"termino": r[0], "definicion": r[1], "ejemplo": r[2], "sinonimos": r[3], "area": r[4]}
            for r in resultados
        ]

    return [{"error": f"No encontrado: {termino}"}]


def listar_por_area(area):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        SELECT termino, definicion FROM biblioteca_vocabulario
        WHERE categoria = 'tecnico' AND area = ?
    """,
        (area,),
    )

    resultados = c.fetchall()
    conn.close()

    return [{"termino": r[0], "definicion": r[1]} for r in resultados]


def todas_areas():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        SELECT DISTINCT area, COUNT(*) as total
        FROM biblioteca_vocabulario
        WHERE categoria = 'tecnico' AND area IS NOT NULL
        GROUP BY area
    """)

    resultados = c.fetchall()
    conn.close()

    return [{"area": r[0], "total": r[1]} for r in resultados]


def explicar_concepto(termino):
    resultado = buscar_termino_tecnico(termino)
    if resultado and "error" not in resultado[0]:
        r = resultado[0]
        return f"""
📚 {r["termino"]}

Definición: {r["definicion"]}

Ejemplo: {r["ejemplo"]}

Sinónimos: {r["sinonimos"]}

Área: {r["area"]}
"""
    return f"Término '{termino}' no encontrado en vocabulario técnico."


if __name__ == "__main__":
    init_vocabulario_tecnico_avanzado()

    print("=== Vocabulario Técnico ===")
    areas = todas_areas()
    print(f"Áreas: {areas}")

    print("\nEjemplo - explicar 'docker':")
    print(explicar_concepto("docker"))
