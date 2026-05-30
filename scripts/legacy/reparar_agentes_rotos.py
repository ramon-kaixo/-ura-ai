#!/usr/bin/env python3
"""Repara los 2 agentes rotos detectados por el catálogo URA usando el
protocolo completo: propuesta → validar → ejecutar.

Bug común en ambos archivos:
- Cuerpo de `procesar` con indentación 4 (debería ser 8).
- Métodos `ejecutar`, `consultar`, `responder` con indentación 0 (fuera de la
  clase) y cuerpos a 4 (deberían ser 4 y 8 respectivamente).
- `responder` con cuerpo vacío.
- `get_agent_capabilities` con `def` sin indentación pero cuerpo correcto.

Estrategia: localizar el rango malformado entre `def procesar` y el siguiente
método con indentación correcta, y re-indentar añadiendo 4 espacios donde
corresponda. Si `responder` está vacío, le añadimos cuerpo estándar.
"""

from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.change_logger import get_change_logger  # noqa: E402
from core.change_proposal_manager import get_change_proposal_manager  # noqa: E402

ARCHIVOS = [
    ROOT / "agents" / "agente_administrativo_contable.py",
    ROOT / "agents" / "agente_creativo_marketing.py",
]


def reparar_contenido(src: str) -> str:
    """Re-indenta el bloque malformado de wrappers.

    Procesa cada sub-bloque que empieza por `def ` dentro del rango problemático
    aplicando las reglas adecuadas según el método.
    """
    lines = src.splitlines(keepends=False)

    # Localizar inicio del bloque malformado.
    start = None
    for i, line in enumerate(lines):
        if re.match(r"^    def procesar\(self, texto: str\) -> str:\s*$", line):
            start = i
            break
    if start is None:
        return src

    # Localizar fin: primer `    def NOMBRE` cuyo nombre no esté en la lista malformada.
    afectados = {"procesar", "ejecutar", "consultar", "responder"}
    end = len(lines)
    for j in range(start + 1, len(lines)):
        m = re.match(r"^    def ([A-Za-z_]\w*)\(", lines[j])
        if m and m.group(1) not in afectados | {"get_agent_capabilities"}:
            end = j
            break

    bloque = lines[start:end]
    nuevo_bloque: list[str] = []

    # Tokenizar en sub-bloques por línea def (con o sin indent).
    def_re = re.compile(r"^( *)def ([A-Za-z_]\w*)\(")

    i = 0
    while i < len(bloque):
        line = bloque[i]
        m = def_re.match(line)
        if not m:
            # Líneas iniciales/blank: pasan tal cual (no debería haber).
            nuevo_bloque.append(line)
            i += 1
            continue

        indent_def, nombre = len(m.group(1)), m.group(2)
        # Recolectar cuerpo hasta el siguiente def (o fin del bloque).
        j = i + 1
        while j < len(bloque) and not def_re.match(bloque[j]):
            j += 1
        cuerpo = bloque[i + 1 : j]

        if nombre in afectados:
            # def: forzar a 4 espacios.
            nuevo_bloque.append("    def " + line.lstrip()[4:])
            # Cuerpo: cada línea no-vacía recibe shift hasta que su primera línea
            # con contenido tenga ≥8 espacios. Calculamos el shift basándonos en
            # la indentación mínima existente en el cuerpo.
            no_vacias = [c for c in cuerpo if c.strip()]
            if not no_vacias:
                # Cuerpo vacío → añadir return self.procesar(texto)
                if nombre == "responder":
                    nuevo_bloque.append('        """Responder consulta delegando en procesar()."""')
                    nuevo_bloque.append("        return self.procesar(texto)")
                else:
                    nuevo_bloque.append("        return self.procesar(texto)")
                # Mantener una línea en blanco si existía.
                if cuerpo and not cuerpo[-1].strip():
                    nuevo_bloque.append("")
            else:
                indent_min = min(len(c) - len(c.lstrip(" ")) for c in no_vacias)
                shift = max(0, 8 - indent_min)
                for c in cuerpo:
                    if not c.strip():
                        nuevo_bloque.append(c)
                    else:
                        nuevo_bloque.append(" " * shift + c)
        elif nombre == "get_agent_capabilities":
            # def: forzar a 4 espacios; cuerpo se mantiene (ya está a 8).
            nuevo_bloque.append("    def " + line.lstrip()[4:])
            for c in cuerpo:
                nuevo_bloque.append(c)
        else:
            # No debería llegar aquí, pero pasa intacto.
            nuevo_bloque.append(line)
            for c in cuerpo:
                nuevo_bloque.append(c)
        i = j

    out = lines[:start] + nuevo_bloque + lines[end:]
    return "\n".join(out) + ("\n" if src.endswith("\n") else "")


def main() -> int:
    manager = get_change_proposal_manager()
    cl = get_change_logger()

    # Generar contenido reparado y validar AST localmente
    contenidos: dict[Path, str] = {}
    for ruta in ARCHIVOS:
        original = ruta.read_text(encoding="utf-8")
        reparado = reparar_contenido(original)
        try:
            ast.parse(reparado)
        except SyntaxError as e:
            print(f"[FAIL] La reparación de {ruta.name} no compila: {e}", file=sys.stderr)
            return 2
        contenidos[ruta] = reparado
        print(f"[OK] Reparación de {ruta.name} compila correctamente.")

    # 1. Crear propuesta
    archivos_rel = [f"agents/{p.name}" for p in ARCHIVOS]
    propuesta = manager.crear_propuesta(
        titulo="Reparar agentes rotos: indentación de wrappers procesar/ejecutar/consultar/responder",
        descripcion=(
            "El catálogo URA detectó dos agentes en estado 'roto' por SyntaxError. "
            "Ambos comparten el mismo patrón de indentación incorrecta en los métodos "
            "wrapper auto-generados (procesar, ejecutar, consultar, responder, "
            "get_agent_capabilities). El cuerpo de procesar tiene 4 espacios cuando "
            "debería tener 8, y los siguientes def están a nivel módulo en lugar de "
            "dentro de la clase. Esta propuesta los re-indenta correctamente y rellena "
            "el cuerpo vacío de responder con `return self.procesar(texto)`. Los "
            "archivos originales se mueven a la papelera del Toshiba antes de aplicar."
        ),
        archivos_afectados=archivos_rel,
        tipo="bugfix",
        autor="ura.maintenance",
    )
    print(f"[1/3] Propuesta creada: {propuesta.id}")

    # 2. Validar
    propuesta = manager.validar_propuesta(propuesta.id)
    print(f"[2/3] Validación: estado={propuesta.estado} motivo={propuesta.motivo_rechazo!r}")
    if propuesta.estado != "aprobada":
        return 3

    # 3. Ejecutar (mueve a papelera y aplica nuevos contenidos vía change_logger)
    def ejecutor(p):
        cambios = []
        for ruta in ARCHIVOS:
            entry = cl.registrar_cambio(
                ruta,
                id_propuesta=p.id,
                tipo="bugfix",
                contenido_nuevo=contenidos[ruta],
                motivo="reparar indentación de wrappers",
            )
            cambios.append(
                {
                    "accion": "reescribir_archivo",
                    "archivo": str(ruta),
                    "papelera": entry.get("papelera", ""),
                }
            )
        return cambios

    propuesta = manager.ejecutar_propuesta(propuesta.id, ejecutor=ejecutor)
    print(f"[3/3] Ejecutada: estado={propuesta.estado} cambios={len(propuesta.ejecutor_cambios)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
