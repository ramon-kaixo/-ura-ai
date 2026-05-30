"""
AGENTE ORQUESTADOR DE DOCUMENTACIÓN
Coordina todos los agentes de documentación, vocabulario y medios.
Gestiona el flujo de documentos y asegura organización.
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"
BIBLIOTECA_PATH = Path(__file__).parent.parent / "biblioteca"

ORQUESTADOR_CONFIG = {
    "formato_agents": {
        "word": {
            "modulo": "agente_documentos_word",
            "clase": "Word",
            "extensiones": [".doc", ".docx"],
        },
        "excel": {
            "modulo": "agente_documentos_excel",
            "clase": "Excel",
            "extensiones": [".xlsx", ".xls", ".csv"],
        },
        "pdf": {"modulo": "agente_documentos_pdf", "clase": "PDF", "extensiones": [".pdf"]},
        "presentaciones": {
            "modulo": "agente_documentos_presentaciones",
            "clase": "Presentaciones",
            "extensiones": [".ppt", ".pptx"],
        },
        "texto": {
            "modulo": "agente_documentos_texto",
            "clase": "Texto",
            "extensiones": [".txt", ".md", ".json", ".log"],
        },
    },
    "vocabulario_agents": {
        "tecnico": {"modulo": "agente_lenguaje_tecnico", "clase": "Tecnico", "area": "Informática"},
        "legal": {"modulo": "agente_vocabulario_legal", "clase": "Legal", "area": "Jurídico"},
        "bar": {"modulo": "agente_vocabulario_bar", "clase": "Bar", "area": "Hostelería"},
        "financiero": {
            "modulo": "agente_vocabulario_financiero",
            "clase": "Financiero",
            "area": "Contabilidad",
        },
        "creativo": {
            "modulo": "agente_lenguaje_creativo",
            "clase": "Creativo",
            "area": "Marketing",
        },
    },
    "media_agents": {
        "fotos": {
            "modulo": "agente_galeria_fotos",
            "clase": "Fotos",
            "extensiones": [".jpg", ".png", ".webp"],
        },
        "videos": {
            "modulo": "agente_galeria_videos",
            "clase": "Videos",
            "extensiones": [".mp4", ".mov"],
        },
    },
}


def init_tablas_orquestador():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS orquesta_documentos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            documento_id INTEGER,
            estado TEXT DEFAULT 'pendiente',
            prioridad INTEGER DEFAULT 5,
            categoria_asignada TEXT,
            etiquetas_sugeridas TEXT,
            acciones_sugeridas TEXT,
            fecha_asignacion TEXT,
            procesado INTEGER DEFAULT 0
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS orquesta_vocabulario (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo_lenguaje TEXT NOT NULL,
            termino TEXT NOT NULL,
            definicion TEXT,
            uso_recomendado TEXT,
            fecha_creacion TEXT NOT NULL
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS orquesta_reglas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            origen TEXT NOT NULL,
            destino TEXT NOT NULL,
            activa INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()


def clasificar_documento(ruta):
    ext = Path(ruta).suffix.lower()
    nombre = Path(ruta).stem.lower()

    categoria = None
    etiquetas = []

    keywords_bar = ["menu", "carta", "plato", "bebida", "tapa", "racion", "copa", "cocina", "barra"]
    keywords_legal = ["factura", "iva", "irpf", "modelo", "contrato", "nómina", "seguridad social"]
    keywords_financiero = [
        "balance",
        "cuenta",
        "pérdidas",
        "ganancias",
        "caja",
        "banco",
        "movimiento",
    ]
    keywords_tecnico = ["codigo", "script", "config", "backup", "database", "api", "servidor"]
    keywords_marketing = ["promo", "oferta", "instagram", "redes", "publicar", "campaign"]

    if any(k in nombre for k in keywords_bar):
        categoria = "bar"
        etiquetas.append("hostelería")
    elif any(k in nombre for k in keywords_legal):
        categoria = "legal"
        etiquetas.append("jurídico")
    elif any(k in nombre for k in keywords_financiero):
        categoria = "financiero"
        etiquetas.append("contabilidad")
    elif any(k in nombre for k in keywords_tecnico):
        categoria = "tecnico"
        etiquetas.append("sistemas")
    elif any(k in nombre for k in keywords_marketing):
        categoria = "marketing"
        etiquetas.append("publicidad")
    else:
        categoria = "general"
        etiquetas.append("sin clasificar")

    return {"categoria": categoria, "etiquetas": etiquetas, "ext": ext}


def sugerir_agente(formato, categoria):
    agentes = {
        ("word", "bar"): "agente_vocabulario_bar",
        ("word", "legal"): "agente_vocabulario_legal",
        ("excel", "financiero"): "agente_vocabulario_financiero",
        ("pdf", "tecnico"): "agente_lenguaje_tecnico",
        ("pdf", "marketing"): "agente_lenguaje_creativo",
        ("texto", "general"): "agente_documentos_texto",
    }

    clave = (formato, categoria)
    if clave in agentes:
        return agentes[clave]

    if formato == "pdf":
        return "agente_documentos_pdf"
    elif formato == "excel":
        return "agente_documentos_excel"
    elif formato == "word":
        return "agente_documentos_word"

    return "agente_biblioteca"


def organizar_documento(ruta_origen, carpeta_destino=None):
    resultado_clasificacion = clasificar_documento(ruta_origen)

    if carpeta_destino is None:
        carpeta_destino = BIBLIOTECA_PATH / resultado_clasificacion["categoria"]

    carpeta_destino.mkdir(parents=True, exist_ok=True)

    nombre_archivo = Path(ruta_origen).name
    ruta_destino = carpeta_destino / nombre_archivo

    try:
        import shutil

        shutil.copy2(ruta_origen, ruta_destino)
        movido = True
    except Exception:
        ruta_destino = ruta_origen
        movido = False

    agente_sugerido = sugerir_agente(
        resultado_clasificacion["ext"].replace(".", ""), resultado_clasificacion["categoria"]
    )

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        """
        INSERT INTO orquesta_documentos
        (estado, prioridad, categoria_asignada, etiquetas_sugeridas, acciones_sugeridas, fecha_asignacion)
        VALUES (?, ?, ?, ?, ?, ?)
    """,
        (
            "organizado" if movido else "ya_ubicado",
            5,
            resultado_clasificacion["categoria"],
            json.dumps(resultado_clasificacion["etiquetas"]),
            agente_sugerido,
            datetime.now().isoformat(),
        ),
    )

    conn.commit()
    conn.close()

    return {
        "original": ruta_origen,
        "destino": str(ruta_destino),
        "categoria": resultado_clasificacion["categoria"],
        "etiquetas": resultado_clasificacion["etiquetas"],
        "agente_sugerido": agente_sugerido,
        "movido": movido,
    }


def revisar_biblioteca():
    resultados = {
        "carpetas": {},
        "documentos_sueltos": [],
        "duplicados": [],
        "sin_categoria": [],
        "acciones_pendientes": 0,
    }

    for carpeta in BIBLIOTECA_PATH.iterdir():
        if carpeta.is_dir():
            archivos = list(carpeta.glob("*"))
            archivos_archivos = [f for f in archivos if f.is_file()]

            nombres = [f.name for f in archivos_archivos]
            duplicados = [n for n in nombres if nombres.count(n) > 1]

            resultados["carpetas"][carpeta.name] = {
                "total": len(archivos_archivos),
                "duplicados": len(set(duplicados)),
            }

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM orquesta_documentos WHERE estado = 'pendiente'")
    resultados["acciones_pendientes"] = c.fetchone()[0]

    conn.close()

    return resultados


def buscar_global(termino):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    resultados = {"documentos": [], "vocabulario": [], "multimedia": []}

    c.execute(
        """
        SELECT nombre, ruta, tipo, formato, etiquetas FROM biblioteca_documentos
        WHERE nombre LIKE ? OR etiquetas LIKE ? OR resumen LIKE ?
    """,
        (f"%{termino}%", f"%{termino}%", f"%{termino}%"),
    )

    for r in c.fetchall():
        resultados["documentos"].append(
            {"nombre": r[0], "ruta": r[1], "tipo": r[2], "formato": r[3], "etiquetas": r[4]}
        )

    c.execute(
        """
        SELECT termino, definicion, categoria FROM biblioteca_vocabulario
        WHERE termino LIKE ? OR definicion LIKE ? OR sinonimos LIKE ?
    """,
        (f"%{termino}%", f"%{termino}%", f"%{termino}%"),
    )

    for r in c.fetchall():
        resultados["vocabulario"].append({"termino": r[0], "definicion": r[1], "categoria": r[2]})

    c.execute(
        """
        SELECT nombre, ruta, tipo, etiquetas FROM biblioteca_multimedia
        WHERE nombre LIKE ? OR etiquetas LIKE ?
    """,
        (f"%{termino}%", f"%{termino}%"),
    )

    for r in c.fetchall():
        resultados["multimedia"].append(
            {"nombre": r[0], "ruta": r[1], "tipo": r[2], "etiquetas": r[3]}
        )

    conn.close()
    return resultados


def status_completo():
    init_tablas_orquestador()

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT COUNT(*) FROM biblioteca_documentos")
    total_docs = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM biblioteca_vocabulario")
    total_vocab = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM biblioteca_multimedia")
    total_media = c.fetchone()[0]

    c.execute("SELECT COUNT(*) FROM orquesta_documentos WHERE procesado = 0")
    pendientes = c.fetchone()[0]

    c.execute("SELECT categoria, COUNT(*) FROM biblioteca_vocabulario GROUP BY categoria")
    vocab_por_cat = dict(c.fetchall())

    conn.close()

    return {
        "documentos": total_docs,
        "vocabulario": total_vocab,
        "multimedia": total_media,
        "tareas_pendientes": pendientes,
        "vocabulario_por_categoria": vocab_por_cat,
        "carpetas": list(BIBLIOTECA_PATH.iterdir()),
        "agentes_configurados": {
            "formato": len(ORQUESTADOR_CONFIG["formato_agents"]),
            "vocabulario": len(ORQUESTADOR_CONFIG["vocabulario_agents"]),
            "media": len(ORQUESTADOR_CONFIG["media_agents"]),
        },
    }


class AgenteOrquestadorDocumentacion:
    """Wrapper para AgenteOrquestadorDocumentacion."""

    def procesar(self, texto: str) -> str:
        """Procesar consulta para AgenteOrquestadorDocumentacion."""
        return "Puedo coordinar documentos y flujo documental. ¿Qué flujo necesitas orquestar?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para AgenteOrquestadorDocumentacion."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para AgenteOrquestadorDocumentacion."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para AgenteOrquestadorDocumentacion."""
        return self.procesar(texto)


if __name__ == "__main__":
    init_tablas_orquestador()

    print("=== ORQUESTADOR DE DOCUMENTACIÓN ===")
    print("\n📊 Status completo:")
    import json

    print(json.dumps(status_completo(), indent=2, default=str))

    print("\n🔍 Revisión biblioteca:")
    print(json.dumps(revisar_biblioteca(), indent=2))
