#!/usr/bin/env python3
"""
Agente Documentador Móvil - URA App
Genera documentación para código generado
"""

from datetime import datetime
from pathlib import Path


class AgenteDocumentador:
    """Genera documentación para código"""

    def __init__(self):
        self.nombre = "agente_documentador"
        self.box_actual = None
        self.doc_path = Path("/Users/ramonesnaola/URA/ura_ia_1972/docs/generado")
        self.doc_path.mkdir(parents=True, exist_ok=True)

    def asignar_box(self, box: str):
        """Asignar agente a un box específico"""
        self.box_actual = box

    def generar_documentacion(
        self, codigo: str, especificacion: str, tipo_codigo: str, box: str = None
    ) -> str:
        """Generar documentación para código"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        doc = f"""# Documentación Generada

**Fecha:** {datetime.now().isoformat()}
**Box:** {box or self.box_actual}
**Tipo de código:** {tipo_codigo}
**Especificación:** {especificacion}
**Contexto:** Código generado por agente móvil

## Código Generado

```python
{codigo}
```

## Metadatos

- Generado por: Agente Universal Móvil
- Box actual: {box or self.box_actual}
- Tipo: {tipo_codigo}
- Requiere revisión antes de producción
- Análisis de vocabulario: Incluido
"""

        # Guardar documentación
        archivo_doc = self.doc_path / f"doc_{timestamp}.md"
        archivo_doc.write_text(doc)

        return str(archivo_doc)

    def generar_readme(self, proyecto: str, descripcion: str) -> str:
        """Generar README para proyecto"""
        readme = f"""# {proyecto}

{descripcion}

## Generado por URA

**Fecha:** {datetime.now().isoformat()}
**Box:** {self.box_actual}

## Estructura

- Documentación generada automáticamente
- Requiere revisión manual
"""

        archivo_readme = self.doc_path / f"README_{proyecto}.md"
        archivo_readme.write_text(readme)

        return str(archivo_readme)


# Instancia global
agente_documentador = AgenteDocumentador()
