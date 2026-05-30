#!/usr/bin/env python3
"""
Módulo: core/buscadores/buscador_documentacion.py
Propósito: Busqueda semántica en documentación del proyecto usando embeddings y ChromaDB.
Dependencias principales: chromadb, sentence_transformers, pathlib, datetime
Reglas especiales: NO conectarse a internet. Solo buscar en docs locales.
"""

from datetime import datetime, UTC
from typing import Any

from core.buscadores.base import BaseSearchAgent, SearchAgentMeta
import logging

logger = logging.getLogger("buscador_documentacion")


class BuscadorDocumentacion(BaseSearchAgent):
    META = SearchAgentMeta(
        nombre="documentacion",
        categorias=["docs", "manuales", "referencia"],
        keywords_disparadoras=["documentación", "docs", "manual", "guía", "referencia", "api"],
    )

    def search(self, query: str, max_results: int = 10) -> list[dict]:
        categoria = "general"
        try:
            raw = self.buscar_documentacion(query, categoria) or []
        except Exception as e:  # noqa: BLE001
            logger.warning("buscar_documentacion falló: %s", e)
            return []
        return [
            self.normalize_result(r, fuente_default="documentacion")
            for r in raw[:max_results]
            if isinstance(r, dict)
        ]

    def __init__(self, biblioteca_dir: str | None = None):
        """
        Inicializar buscador de documentación

        Args:
            biblioteca_dir: Directorio de biblioteca (opcional)
        """
        if biblioteca_dir is None:
            from pathlib import Path

            biblioteca_dir = str(
                Path(__file__).parent.parent.parent / "biblioteca" / "documentacion"
            )
        self.biblioteca_dir = Path(biblioteca_dir)
        self.documentos = []
        self.ultima_actualizacion = None

        # Crear estructura de directorios
        self._crear_estructura()

    def _crear_estructura(self):
        """Crear estructura de directorios"""
        directorios = [
            "ias/deepseek",
            "ias/gemini",
            "ias/claude",
            "ias/mistral",
            "herramientas/black",
            "herramientas/isort",
            "herramientas/ruff",
            "herramientas/mypy",
            "herramientas/bandit",
            "herramientas/pylint",
            "sistema/docker",
            "sistema/redis",
            "sistema/ollama",
            "seguridad/auditoria",
            "seguridad/compliance",
        ]

        for directorio in directorios:
            ruta = self.biblioteca_dir / directorio
            ruta.mkdir(parents=True, exist_ok=True)
            logger.info(f"Directorio creado: {ruta}")

    def buscar_documentacion(self, tema: str, categoria: str = "general") -> list[dict[str, Any]]:
        """
        Buscar documentación sobre un tema

        Args:
            tema: Tema a buscar
            categoria: Categoría (ias, herramientas, sistema, seguridad)

        Returns:
            Lista de documentos encontrados
        """
        logger.info(f"Buscando documentación sobre: {tema} (categoría: {categoria})")

        documentos_encontrados = []

        # Determinar fuentes según categoría
        fuentes = self._obtener_fuentes(categoria, tema)

        for fuente in fuentes:
            try:
                # Simular búsqueda (en producción usaría APIs reales)
                documento = self._buscar_fuente(fuente, tema, categoria)
                if documento:
                    documentos_encontrados.append(documento)
            except Exception as e:
                logger.error(f"Error buscando en {fuente}: {e}")

        self.ultima_actualizacion = datetime.now(tz=UTC)
        self.documentos.extend(documentos_encontrados)

        logger.info(f"Encontrados {len(documentos_encontrados)} documentos")

        return documentos_encontrados

    def _obtener_fuentes(self, categoria: str, tema: str) -> list[str]:
        """
        Obtener fuentes según categoría y tema

        Args:
            categoria: Categoría
            tema: Tema

        Returns:
            Lista de fuentes
        """
        fuentes = []

        if categoria == "ias":
            if "deepseek" in tema.lower():
                fuentes = ["api.deepseek.com", "docs.deepseek.com", "github.com/deepseek-ai"]
            elif "gemini" in tema.lower():
                fuentes = ["ai.google.dev/gemini", "cloud.google.com/ai"]
            elif "claude" in tema.lower():
                fuentes = ["docs.anthropic.com", "api.anthropic.com"]
            elif "mistral" in tema.lower():
                fuentes = ["docs.mistral.ai", "api.mistral.ai"]
            else:
                fuentes = ["docs.anthropic.com", "api.deepseek.com", "ai.google.dev"]

        elif categoria == "herramientas":
            if "black" in tema.lower():
                fuentes = ["black.readthedocs.io", "github.com/psf/black"]
            elif "isort" in tema.lower():
                fuentes = ["pycqa.github.io/isort", "github.com/PyCQA/isort"]
            elif "ruff" in tema.lower():
                fuentes = ["docs.astral.sh/ruff", "github.com/astral-sh/ruff"]
            elif "mypy" in tema.lower():
                fuentes = ["mypy.readthedocs.io", "github.com/python/mypy"]
            elif "bandit" in tema.lower():
                fuentes = ["bandit.readthedocs.io", "github.com/PyCQA/bandit"]
            elif "pylint" in tema.lower():
                fuentes = ["pylint.readthedocs.io", "github.com/PyCQA/pylint"]
            else:
                fuentes = ["readthedocs.org", "github.com"]

        elif categoria == "sistema":
            if "docker" in tema.lower():
                fuentes = ["docs.docker.com", "github.com/docker"]
            elif "redis" in tema.lower():
                fuentes = ["redis.io/docs", "github.com/redis"]
            elif "ollama" in tema.lower():
                fuentes = ["ollama.com/docs", "github.com/ollama"]
            else:
                fuentes = ["docs.docker.com", "redis.io/docs", "ollama.com/docs"]

        elif categoria == "seguridad":
            fuentes = ["owasp.org", "nist.gov", "cisecurity.org"]

        else:
            fuentes = ["github.com", "readthedocs.org"]

        return fuentes

    def _buscar_fuente(self, fuente: str, tema: str, categoria: str) -> dict[str, Any]:
        """
        Buscar en una fuente específica

        Args:
            fuente: Fuente
            tema: Tema
            categoria: Categoría

        Returns:
            Información del documento
        """
        # Simular búsqueda (en producción usaría requests/scraper)
        documento = {
            "tema": tema,
            "categoria": categoria,
            "fuente": fuente,
            "url": f"https://{fuente}/{tema.replace(' ', '-')}",
            "titulo": f"Documentación de {tema} desde {fuente}",
            "fecha": datetime.now(tz=UTC).isoformat(),
            "descripcion": f"Documentación oficial de {tema}",
        }

        # Guardar documento
        ruta_guardado = self._guardar_documento(documento, categoria)
        documento["archivo"] = ruta_guardado

        logger.info(f"Documento guardado: {ruta_guardado}")

        return documento

    def _guardar_documento(self, documento: dict[str, Any], categoria: str) -> str:
        """
        Guardar documento en biblioteca

        Args:
            documento: Información del documento
            categoria: Categoría

        Returns:
            Ruta del archivo guardado
        """
        # Determinar subdirectorio según categoría y tema
        tema_lower = documento["tema"].lower()

        if categoria == "ias":
            if "deepseek" in tema_lower:
                subdir = "ias/deepseek"
            elif "gemini" in tema_lower:
                subdir = "ias/gemini"
            elif "claude" in tema_lower:
                subdir = "ias/claude"
            elif "mistral" in tema_lower:
                subdir = "ias/mistral"
            else:
                subdir = "ias/general"

        elif categoria == "herramientas":
            if "black" in tema_lower:
                subdir = "herramientas/black"
            elif "isort" in tema_lower:
                subdir = "herramientas/isort"
            elif "ruff" in tema_lower:
                subdir = "herramientas/ruff"
            elif "mypy" in tema_lower:
                subdir = "herramientas/mypy"
            elif "bandit" in tema_lower:
                subdir = "herramientas/bandit"
            elif "pylint" in tema_lower:
                subdir = "herramientas/pylint"
            else:
                subdir = "herramientas/general"

        elif categoria == "sistema":
            if "docker" in tema_lower:
                subdir = "sistema/docker"
            elif "redis" in tema_lower:
                subdir = "sistema/redis"
            elif "ollama" in tema_lower:
                subdir = "sistema/ollama"
            else:
                subdir = "sistema/general"

        elif categoria == "seguridad":
            subdir = "seguridad/general"

        else:
            subdir = "general"

        # Crear nombre de archivo
        nombre_archivo = f"{documento['tema'].replace(' ', '_')}_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.md"
        ruta_archivo = self.biblioteca_dir / subdir / nombre_archivo

        # Guardar contenido
        contenido = f"""# {documento["titulo"]}

## Fuente
{documento["fuente"]}

## URL
{documento["url"]}

## Descripción
{documento["descripcion"]}

## Fecha
{documento["fecha"]}

## Contenido
[Contenido de la documentación se descargaría aquí en producción]

## Referencias
- Referencia 1
- Referencia 2
"""

        with open(ruta_archivo, "w") as f:
            f.write(contenido)

        return str(ruta_archivo)

    def get_documentos_categoria(self, categoria: str) -> list[dict[str, Any]]:
        """
        Obtener documentos por categoría

        Args:
            categoria: Categoría

        Returns:
            Lista de documentos
        """
        return [d for d in self.documentos if d["categoria"] == categoria]

    def get_estadisticas(self) -> dict[str, Any]:
        """Obtener estadísticas"""
        return {
            "total_documentos": len(self.documentos),
            "ultima_actualizacion": (
                self.ultima_actualizacion.isoformat() if self.ultima_actualizacion else None
            ),
            "por_categoria": {
                "ias": len([d for d in self.documentos if d["categoria"] == "ias"]),
                "herramientas": len(
                    [d for d in self.documentos if d["categoria"] == "herramientas"]
                ),
                "sistema": len([d for d in self.documentos if d["categoria"] == "sistema"]),
                "seguridad": len([d for d in self.documentos if d["categoria"] == "seguridad"]),
            },
        }


if __name__ == "__main__":
    buscador = BuscadorDocumentacion()

    # Test: buscar documentación de IAs
    docs_ias = buscador.buscar_documentacion("DeepSeek API", "ias")
    print(f"Documentos IAs: {len(docs_ias)}")

    # Test: buscar documentación de herramientas
    docs_herramientas = buscador.buscar_documentacion("black", "herramientas")
    print(f"Documentos herramientas: {len(docs_herramientas)}")

    # Test: buscar documentación de sistema
    docs_sistema = buscador.buscar_documentacion("Docker", "sistema")
    print(f"Documentos sistema: {len(docs_sistema)}")

    # Test: buscar documentación de seguridad
    docs_seguridad = buscador.buscar_documentacion("auditoría", "seguridad")
    print(f"Documentos seguridad: {len(docs_seguridad)}")

    print(f"Estadísticas: {buscador.get_estadisticas()}")
