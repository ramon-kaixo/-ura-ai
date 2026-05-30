#!/usr/bin/env python3
"""
AGENTE FORMULARIOS — Genera y procesa formularios.

Crea formularios dinámicos, valida datos de entrada, genera plantillas
HTML/JSON y procesa respuestas de formularios para integración con URA.
"""

import json
import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

SISTEMA = Path(__file__).parent.parent
LOG_DIR = SISTEMA / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG = LOG_DIR / "formularios.log"
DB_PATH = SISTEMA / "board.db"

TIPOS_CAMPO = {
    "texto": {"html": "text", "validacion": r"^.+$"},
    "email": {"html": "email", "validacion": r"^[\w.-]+@[\w.-]+\.\w+$"},
    "telefono": {"html": "tel", "validacion": r"^\+?\d{7,15}$"},
    "numero": {"html": "number", "validacion": r"^-?\d+\.?\d*$"},
    "fecha": {"html": "date", "validacion": r"^\d{4}-\d{2}-\d{2}$"},
    "hora": {"html": "time", "validacion": r"^\d{2}:\d{2}(:\d{2})?$"},
    "url": {"html": "url", "validacion": r"^https?://\S+$"},
    "textarea": {"html": "textarea", "validacion": r"^.+$"},
    "select": {"html": "select", "validacion": None},
    "checkbox": {"html": "checkbox", "validacion": None},
    "cif": {"html": "text", "validacion": r"^[A-Z]\d{7}[A-Z0-9]$"},
    "nif": {"html": "text", "validacion": r"^\d{8}[A-Z]$"},
    "iban": {"html": "text", "validacion": r"^ES\d{22}$"},
}

PLANTILLAS = {
    "factura": [
        {"nombre": "cliente", "tipo": "texto", "requerido": True, "label": "Cliente"},
        {"nombre": "cif", "tipo": "cif", "requerido": True, "label": "CIF/NIF"},
        {"nombre": "concepto", "tipo": "textarea", "requerido": True, "label": "Concepto"},
        {
            "nombre": "base_imponible",
            "tipo": "numero",
            "requerido": True,
            "label": "Base imponible (€)",
        },
        {
            "nombre": "iva",
            "tipo": "select",
            "requerido": True,
            "label": "IVA %",
            "opciones": ["21", "10", "4", "0"],
        },
        {"nombre": "fecha", "tipo": "fecha", "requerido": True, "label": "Fecha emisión"},
    ],
    "contacto": [
        {"nombre": "nombre", "tipo": "texto", "requerido": True, "label": "Nombre"},
        {"nombre": "email", "tipo": "email", "requerido": True, "label": "Email"},
        {"nombre": "telefono", "tipo": "telefono", "requerido": False, "label": "Teléfono"},
        {"nombre": "mensaje", "tipo": "textarea", "requerido": True, "label": "Mensaje"},
    ],
    "empleado": [
        {"nombre": "nombre", "tipo": "texto", "requerido": True, "label": "Nombre completo"},
        {"nombre": "nif", "tipo": "nif", "requerido": True, "label": "NIF"},
        {"nombre": "email", "tipo": "email", "requerido": True, "label": "Email"},
        {"nombre": "puesto", "tipo": "texto", "requerido": True, "label": "Puesto"},
        {"nombre": "fecha_alta", "tipo": "fecha", "requerido": True, "label": "Fecha de alta"},
        {
            "nombre": "salario",
            "tipo": "numero",
            "requerido": False,
            "label": "Salario bruto anual (€)",
        },
    ],
    "proveedor": [
        {"nombre": "empresa", "tipo": "texto", "requerido": True, "label": "Empresa"},
        {"nombre": "cif", "tipo": "cif", "requerido": True, "label": "CIF"},
        {"nombre": "contacto", "tipo": "texto", "requerido": True, "label": "Persona de contacto"},
        {"nombre": "email", "tipo": "email", "requerido": True, "label": "Email"},
        {"nombre": "telefono", "tipo": "telefono", "requerido": False, "label": "Teléfono"},
        {"nombre": "iban", "tipo": "iban", "requerido": False, "label": "IBAN"},
    ],
}


def _log(msg: str) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG, "a") as f:
        f.write(f"[{ts}] {msg}\n")
    logger.info(msg)


class AgenteFormularios:
    """Genera y procesa formularios dinámicos."""

    def __init__(self) -> None:
        self.formularios_dir = SISTEMA / "formularios"
        self.formularios_dir.mkdir(exist_ok=True)

    def generar_formulario(
        self, nombre: str, campos: list | None = None, plantilla: str | None = None
    ) -> dict:
        """Genera un formulario JSON con validaciones."""
        if plantilla and plantilla in PLANTILLAS:
            campos = PLANTILLAS[plantilla]
            _log(f"Usando plantilla '{plantilla}' con {len(campos)} campos")

        if not campos:
            return {"ok": False, "error": "No se proporcionaron campos ni plantilla válida"}

        formulario = {
            "id": f"form_{nombre}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "nombre": nombre,
            "creado": datetime.now().isoformat(),
            "campos": [],
        }

        for campo in campos:
            tipo_info = TIPOS_CAMPO.get(campo.get("tipo", "texto"), TIPOS_CAMPO["texto"])
            campo_def = {
                "nombre": campo["nombre"],
                "label": campo.get("label", campo["nombre"]),
                "tipo": campo.get("tipo", "texto"),
                "html_type": tipo_info["html"],
                "requerido": campo.get("requerido", False),
                "validacion": tipo_info.get("validacion"),
            }
            if "opciones" in campo:
                campo_def["opciones"] = campo["opciones"]
            formulario["campos"].append(campo_def)

        form_path = self.formularios_dir / f"{formulario['id']}.json"
        with open(form_path, "w") as f:
            json.dump(formulario, f, indent=2, ensure_ascii=False)

        _log(f"Formulario generado: {form_path}")
        return {"ok": True, "formulario": formulario, "path": str(form_path)}

    def generar_html(self, formulario: dict) -> str:
        """Genera HTML para un formulario."""
        campos_html = []
        for campo in formulario.get("campos", []):
            req = " required" if campo.get("requerido") else ""
            label = campo.get("label", campo["nombre"])
            name = campo["nombre"]

            if campo["html_type"] == "textarea":
                input_html = f'<textarea name="{name}" rows="4"{req}></textarea>'
            elif campo["html_type"] == "select":
                opts = "".join(
                    f'<option value="{o}">{o}</option>' for o in campo.get("opciones", [])
                )
                input_html = f'<select name="{name}"{req}>{opts}</select>'
            elif campo["html_type"] == "checkbox":
                input_html = f'<input type="checkbox" name="{name}">'
            else:
                input_html = f'<input type="{campo["html_type"]}" name="{name}"{req}>'

            campos_html.append(f'<div class="campo"><label>{label}</label>{input_html}</div>')

        return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{formulario.get("nombre", "Formulario")}</title>
<style>body{{font-family:sans-serif;max-width:600px;margin:40px auto;padding:0 20px}}
.campo{{margin:15px 0}}label{{display:block;font-weight:bold;margin-bottom:5px}}
input,textarea,select{{width:100%;padding:8px;border:1px solid #ccc;border-radius:4px}}
button{{background:#007bff;color:#fff;padding:10px 20px;border:none;border-radius:4px;cursor:pointer}}</style>
</head><body><h2>{formulario.get("nombre", "Formulario")}</h2>
<form method="post">{"".join(campos_html)}<div class="campo"><button type="submit">Enviar</button></div></form></body></html>"""

    def validar_datos(self, formulario: dict, datos: dict) -> dict:
        """Valida datos contra un formulario."""
        errores = []
        datos_limpios = {}

        for campo in formulario.get("campos", []):
            nombre = campo["nombre"]
            valor = (
                datos.get(nombre, "").strip()
                if isinstance(datos.get(nombre), str)
                else datos.get(nombre)
            )

            if campo.get("requerido") and not valor:
                errores.append(f"{campo.get('label', nombre)}: campo requerido")
                continue

            if valor and campo.get("validacion"):
                if not re.match(campo["validacion"], str(valor)):
                    errores.append(f"{campo.get('label', nombre)}: formato inválido")
                    continue

            if valor:
                datos_limpios[nombre] = valor

        return {
            "ok": len(errores) == 0,
            "errores": errores,
            "datos_validados": datos_limpios,
        }

    def guardar_respuesta(self, formulario_id: str, datos: dict) -> dict:
        """Guarda una respuesta de formulario en la BD."""
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("""
                CREATE TABLE IF NOT EXISTS formularios_respuestas (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    formulario_id TEXT NOT NULL,
                    datos TEXT NOT NULL,
                    timestamp TEXT NOT NULL
                )
            """)
            c.execute(
                "INSERT INTO formularios_respuestas (formulario_id, datos, timestamp) VALUES (?, ?, ?)",
                (formulario_id, json.dumps(datos, ensure_ascii=False), datetime.now().isoformat()),
            )
            conn.commit()
            conn.close()
            _log(f"Respuesta guardada para formulario {formulario_id}")
            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def listar_plantillas(self) -> dict:
        """Lista las plantillas disponibles."""
        return {
            "plantillas": {
                k: {"campos": len(v), "detalle": [c["label"] for c in v]}
                for k, v in PLANTILLAS.items()
            }
        }

    def ejecutar(self, tarea: str = "listar", **kwargs) -> dict:
        """Punto de entrada principal."""
        _log(f"Ejecutando: {tarea}")

        if tarea == "listar":
            return self.listar_plantillas()
        elif tarea == "generar":
            return self.generar_formulario(
                kwargs.get("nombre", "formulario"),
                plantilla=kwargs.get("plantilla"),
                campos=kwargs.get("campos"),
            )
        elif tarea == "validar":
            return self.validar_datos(kwargs.get("formulario", {}), kwargs.get("datos", {}))

        return {"error": f"Tarea desconocida: {tarea}"}


def ejecutar(tarea: str = "listar", **kwargs) -> dict:
    """Función de entrada para el orquestador."""
    agente = AgenteFormularios()
    return agente.ejecutar(tarea, **kwargs)


if __name__ == "__main__":
    import sys

    tarea = sys.argv[1] if len(sys.argv) > 1 else "listar"
    resultado = ejecutar(tarea)
    print(json.dumps(resultado, indent=2, default=str, ensure_ascii=False))
