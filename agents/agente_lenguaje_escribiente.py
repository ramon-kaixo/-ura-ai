"""
AGENTE LENGUAJE / ESCRIBIENTE - Redacta textos, informes y documentación
"""

import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

PLANTILLAS_INFORMES = {
    "diario": """# INFORME DIARIO URA
## Fecha: {fecha}

### Resumen del día
{resumen}

### Tareas completadas
{tareas}

### Incidencias
{incidencias}

### Próximas acciones
{ proximas}

---
*Generado por URA - Agente Lenguaje*
""",
    "semanal": """# INFORME SEMANAL URA
## Semana: {semana}

### Estadísticas
- Tareas completadas: {tareas_completadas}
- Incidencias: {incidencias}
- Servicios activos: {servicios}

### Análisis
{analisis}

### Recomendaciones
{recomendaciones}

---
*Generado por URA - Agente Lenguaje*
""",
    "incidencia": """# REPORTE DE INCIDENCIA
## ID: {id}
## Fecha: {fecha}

### Descripción
{descripcion}

### Causa raíz
{causa}

### Solución aplicada
{solucion}

### Resultado
{resultado}

---
*Documentado por URA*
""",
    "proyecto": """# PROYECTO: {nombre}
## Inicio: {inicio}

## Descripción
{descripcion}

## Requerimientos
{requerimientos}

## Arquitectura
{arquitectura}

## Estado actual
{estado}

## Próximos pasos
{ proximos}

---
*Creado por URA - Agente Lenguaje*
""",
}


def redactar_informe(tipo, datos):
    """Genera un informe desde plantilla"""
    if tipo not in PLANTILLAS_INFORMES:
        return {"error": f"Plantilla '{tipo}' no encontrada"}

    plantilla = PLANTILLAS_INFORMES[tipo]

    try:
        informe = plantilla.format(**datos)

        # Guardar en BD
        guardar_informe(tipo, datos.get("fecha", datetime.now().isoformat()[:10]), informe)

        return {"success": True, "informe": informe}
    except KeyError as e:
        return {"error": f"Falta dato: {e}"}


def guardar_informe(tipo, fecha, contenido):
    """Guarda informe en BD"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS informes_generados (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            fecha TEXT,
            contenido TEXT,
            created_at TEXT NOT NULL
        )
    """)

    c.execute(
        """
        INSERT INTO informes_generados (tipo, fecha, contenido, created_at)
        VALUES (?, ?, ?, ?)
    """,
        (tipo, fecha, contenido[:5000], datetime.now().isoformat()),
    )

    conn.commit()
    conn.close()


def listar_informes(tipo=None, limite=20):
    """Lista informes generados"""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    if tipo:
        c.execute(
            """
            SELECT id, tipo, fecha, substr(contenido, 1, 100), created_at
            FROM informes_generados
            WHERE tipo = ?
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (tipo, limite),
        )
    else:
        c.execute(
            """
            SELECT id, tipo, fecha, substr(contenido, 1, 100), created_at
            FROM informes_generados
            ORDER BY created_at DESC
            LIMIT ?
        """,
            (limite,),
        )

    return c.fetchall()


def generar_acta_reunion(datos):
    """Genera acta de reunión"""
    newline = "\n"
    return f"""# ACTA DE REUNIÓN
## Fecha: {datos.get("fecha", datetime.now().date())}
## Asistentes: {datos.get("asistentes", "TBD")}
## Duración: {datos.get("duracion", "TBD")}

---

## ORDEN DEL DÍA
{datos.get("orden_dia", f"1.{newline}2.{newline}3.")}

---

## DESARROLLO

### Punto 1
{datos.get("punto1", "")}

### Punto 2
{datos.get("punto2", "")}

---

## ACUERDOS
{datos.get("acuerdos", "")}

---

## PRÓXIMA REUNIÓN
{datos.get("proxima", "Por determinar")}

---

Firmado: _________________
Fecha: {datetime.now().date()}
"""


def generar_documento_tecnico(nombre, specs):
    """Genera documentación técnica"""
    specs = specs or {}
    return f"""# DOCUMENTACIÓN TÉCNICA
## {nombre}

### 1. DESCRIPCIÓN
{specs.get("descripcion", "N/A")}

### 2. ESPECIFICACIONES
{specs.get("especificaciones", "N/A")}

### 3. INSTALACIÓN
```
{specs.get("instalacion", "# comandos de instalación")}
```

### 4. USO
{specs.get("uso", "N/A")}

### 5. TROUBLESHOOTING
{specs.get("troubleshooting", "N/A")}

---

*Documentado por URA - {datetime.now().date()}*
"""


def resumir_texto(texto, max_palabras=50):
    """Resume un texto largo"""
    palabras = texto.split()
    if len(palabras) <= max_palabras:
        return texto

    resumen = " ".join(palabras[:max_palabras])
    return resumen + "..."


def corregir_texto(texto):
    """Corrige mayúsculas y puntuación básica"""
    # Primera letra mayúscula
    if texto and texto[0].islower():
        texto = texto[0].upper() + texto[1:]

    # Punto final si no lo tiene
    if texto and texto[-1] not in ".!?":
        texto += "."

    # Espacios múltiples
    while "  " in texto:
        texto = texto.replace("  ", " ")

    return texto


def formatear_codigo(codigo, lenguaje="python"):
    """Formatea código para documentación"""
    return f"```{lenguaje}\n{codigo}\n```"


def generar_nota_accion(agente, accion, resultado):
    """Genera nota de acción para auditoría"""
    return f"""## NOTA DE ACCIÓN
- **Agente**: {agente}
- **Acción**: {accion}
- **Resultado**: {resultado}
- **Fecha**: {datetime.now().isoformat()}
- **Usuario**: Sistema URA
"""


if __name__ == "__main__":
    print("=== AGENTE LENGUAJE / ESCRIBIENTE ===")

    # Generar informe diario de ejemplo
    resultado = redactar_informe(
        "diario",
        {
            "fecha": datetime.now().date(),
            "resumen": "Día de configuración de URA",
            "tareas": "1. Agentes creados\n2. Supervisión activada",
            "incidencias": "Ninguna",
            "proximo": "1. Integrar más agentes\n2. Probar autonomía",
        },
    )

    if "success" in resultado:
        print("✅ Informe generado")
        print(resultado["informe"][:500] + "...")
    else:
        print(f"❌ Error: {resultado}")
