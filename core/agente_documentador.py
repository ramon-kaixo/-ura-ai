"""
Módulo: core/agente_documentador.py
Propósito: Cataloga y documenta automáticamente todos los agentes del ecosistema URA usando análisis AST.
Dependencias principales: ast, json, pathlib, importlib
Reglas especiales: No ejecuta código externo; solo lee y analiza estructura de archivos.
"""

from __future__ import annotations

import ast
import datetime as _dt
import json
import logging
import re
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(__file__).resolve().parent / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
CATALOG_PATH = DATA_DIR / "catalogo_ura.json"

# Heurísticas de intención por nombre de agente
_INTENT_KEYWORDS = {
    "policia": "validacion_seguridad",
    "guardian": "supervision_proteccion",
    "maestro": "orquestacion_central",
    "verificador": "verificacion_grupos",
    "revisor": "revision_codigo",
    "auditor": "auditoria",
    "documentador": "catalogacion_documentacion",
    "documentacion": "documentacion",
    "documentos": "gestion_documental",
    "cocina": "asesoria_culinaria",
    "facturas": "gestion_facturacion",
    "banco": "gestion_bancaria",
    "contabilidad": "contabilidad",
    "asesor": "asesoria",
    "biblioteca": "gestion_conocimiento",
    "vision": "vision_artificial",
    "gui": "interfaz_grafica",
    "camaras": "vigilancia_video",
    "email": "gestion_correo",
    "conversacion": "dialogo_natural",
    "automatiz": "automatizacion",
    "automatizac": "automatizacion",
    "backup": "respaldo_datos",
    "seguridad": "seguridad_sistema",
    "creativo": "generacion_contenido",
    "investigador": "investigacion",
    "traductor": "traduccion",
    "salud": "salud_bienestar",
    "viajes": "planificacion_viajes",
    "compras": "gestion_compras",
    "galeria": "gestion_imagenes",
    "musica": "gestion_audio",
    "tareas": "gestion_tareas",
    "memoria": "memoria_largo_plazo",
    "conciencia": "metacognicion",
    "conectividad": "red_conectividad",
    "archivist": "archivado",
    "arquitectura": "arquitectura_sistema",
}


def _detectar_intencion(nombre: str, docstring: str) -> str:
    nombre_lower = nombre.lower()
    for kw, intent in _INTENT_KEYWORDS.items():
        if kw in nombre_lower:
            return intent
    if docstring:
        primera = docstring.strip().split("\n", 1)[0].strip()
        if primera:
            return primera[:80]
    return "no_especificada"


def _parse_python(path: Path) -> ast.Module | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"No se pudo parsear {path}: {e}")
        return None


def _imports_de_modulo(tree: ast.Module) -> list[str]:
    deps: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                deps.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                top = node.module.lstrip(".").split(".")[0]
                if top:
                    deps.add(top)
    # Solo nos interesan dependencias internas + algunas externas relevantes
    return sorted(deps)


def _public_methods(class_node: ast.ClassDef) -> list[str]:
    out: list[str] = []
    for item in class_node.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not item.name.startswith("_"):
                out.append(item.name)
    return out


# --------------------------------------------------------------------------
class AgenteDocumentador:
    """Catálogo del ecosistema URA."""

    def __init__(
        self,
        project_root: Path | None = None,
        catalog_path: Path | None = None,
    ) -> None:
        self.project_root = Path(project_root) if project_root else PROJECT_ROOT
        self.catalog_path = Path(catalog_path) if catalog_path else CATALOG_PATH
        self._catalog: dict = {}

    # ------------------------------------------------------------
    # Catalogación: AGENTES
    # ------------------------------------------------------------
    def catalogar_agentes(self) -> dict:
        agents_dir = self.project_root / "agents"
        out: dict[str, dict] = {}
        if not agents_dir.exists():
            return out
        for py in sorted(agents_dir.glob("agente_*.py")):
            nombre = py.stem
            tree = _parse_python(py)
            entry: dict = {
                "ruta": str(py.relative_to(self.project_root)),
                "clase": None,
                "metodos": [],
                "intencion": "no_especificada",
                "dependencias": [],
                "estado": "activo",
                "docstring": "",
            }
            if tree is None:
                entry["estado"] = "roto"
                entry["intencion"] = _detectar_intencion(nombre, "")
                out[nombre] = entry
                continue

            module_doc = ast.get_docstring(tree) or ""
            entry["docstring"] = module_doc.strip().split("\n", 1)[0][:200]
            entry["dependencias"] = _imports_de_modulo(tree)

            # Buscar la clase principal: primero la más PascalCase
            classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
            principal: ast.ClassDef | None = None
            for c in classes:
                if c.name.lower().startswith("agente"):
                    principal = c
                    break
            if principal is None and classes:
                principal = classes[0]

            if principal is not None:
                entry["clase"] = principal.name
                entry["metodos"] = _public_methods(principal)
                cls_doc = ast.get_docstring(principal) or ""
                entry["intencion"] = _detectar_intencion(nombre, cls_doc or module_doc)
            else:
                entry["estado"] = "inactivo"  # Archivo sin clase
                entry["intencion"] = _detectar_intencion(nombre, module_doc)

            out[nombre] = entry
        return out

    # ------------------------------------------------------------
    # Catalogación: MÓDULOS
    # ------------------------------------------------------------
    def catalogar_modulos(self) -> dict:
        targets: list[Path] = []
        for sub in ("core", "connectors", "scripts"):
            d = self.project_root / sub
            if d.exists():
                targets.extend(sorted(d.rglob("*.py")))
        # Archivos sueltos relevantes en raíz
        for nombre in ("main_final.py", "ura_panel.py"):
            p = self.project_root / nombre
            if p.exists():
                targets.append(p)

        excluir = {".venv", "__pycache__", ".pytest_cache", ".ruff_cache"}
        out: dict[str, dict] = {}
        for py in targets:
            if any(part in excluir for part in py.parts):
                continue
            rel = str(py.relative_to(self.project_root))
            tree = _parse_python(py)
            entry = {
                "ruta": rel,
                "proposito": "",
                "dependencias": [],
                "estado": "activo",
            }
            if tree is None:
                entry["estado"] = "roto"
                out[py.stem] = entry
                continue
            doc = ast.get_docstring(tree) or ""
            entry["proposito"] = doc.strip().split("\n", 1)[0][:200]
            entry["dependencias"] = _imports_de_modulo(tree)
            # Clave única: usar ruta relativa para evitar colisiones
            key = rel.replace("/", ".").removesuffix(".py")
            out[key] = entry
        return out

    # ------------------------------------------------------------
    # Catalogación: APLICACIONES (macOS)
    # ------------------------------------------------------------
    def catalogar_aplicaciones(self) -> dict:
        candidatos = [
            (
                "Ollama",
                ["/Applications/Ollama.app", "/usr/local/bin/ollama", "/opt/homebrew/bin/ollama"],
                "modelos_locales",
            ),
            (
                "OpenClaw",
                ["/opt/homebrew/bin/openclaw", "/usr/local/bin/openclaw"],
                "agente_remoto_skills",
            ),
            ("Windsurf", ["/Applications/Windsurf.app"], "ide_pair_programming"),
            ("URA", ["/Users/ramonesnaola/Desktop/URA.app"], "lanzador_ura"),
        ]
        out: dict[str, dict] = {}
        for nombre, rutas, proposito in candidatos:
            ruta_encontrada = next((r for r in rutas if Path(r).exists()), None)
            if ruta_encontrada is None:
                out[nombre] = {
                    "ruta": "",
                    "version": "",
                    "proposito": proposito,
                    "estado": "no_instalado",
                }
                continue
            version = self._detectar_version(nombre, ruta_encontrada)
            out[nombre] = {
                "ruta": ruta_encontrada,
                "version": version,
                "proposito": proposito,
                "estado": "instalado",
            }
        return out

    def _detectar_version(self, nombre: str, ruta: str) -> str:
        # Comandos CLI
        cli_map = {
            "Ollama": ["ollama", "--version"],
            "OpenClaw": ["openclaw", "--version"],
        }
        if nombre in cli_map:
            try:
                r = subprocess.run(cli_map[nombre], capture_output=True, text=True, timeout=5)
                txt = (r.stdout + r.stderr).strip()
                m = re.search(r"\d+\.\d+(?:\.\d+)?", txt)
                if m:
                    return m.group(0)
                return txt.splitlines()[0][:50] if txt else ""
            except Exception:
                return ""
        # Apps con Info.plist
        if ruta.endswith(".app"):
            plist = Path(ruta) / "Contents" / "Info.plist"
            if plist.exists():
                try:
                    r = subprocess.run(
                        ["defaults", "read", str(plist), "CFBundleShortVersionString"],
                        capture_output=True,
                        text=True,
                        timeout=3,
                    )
                    return r.stdout.strip() or ""
                except Exception:
                    return ""
        return ""

    # ------------------------------------------------------------
    # Catalogación: SCREENS
    # ------------------------------------------------------------
    def catalogar_screens(self) -> dict:
        """Detecta archivos *_screen.py o referencias a 'screen' en agentes vision/gui."""
        out: dict[str, dict] = {}
        # 1. Archivos con nombre *_screen.py o splash_screen, etc.
        for py in self.project_root.rglob("*screen*.py"):
            if any(part in {".venv", "__pycache__", ".git"} for part in py.parts):
                continue
            rel = str(py.relative_to(self.project_root))
            tree = _parse_python(py)
            doc = (ast.get_docstring(tree) if tree else "") or ""
            agente = ""
            for ag in ("vision", "gui", "camaras"):
                if ag in rel.lower():
                    agente = f"agente_{ag}"
                    break
            out[py.stem] = {
                "ruta": rel,
                "proposito": doc.strip().split("\n", 1)[0][:200] or "interfaz_visual",
                "agente_asociado": agente or "ui_general",
            }
        # 2. Buscar configuración explícita de screens en agentes vision/gui
        for nombre in ("agente_vision", "agente_gui"):
            p = self.project_root / "agents" / f"{nombre}.py"
            if not p.exists():
                continue
            tree = _parse_python(p)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.Assign):
                    for t in node.targets:
                        if isinstance(t, ast.Name) and "screen" in t.id.lower():
                            out[f"{nombre}.{t.id}"] = {
                                "ruta": str(p.relative_to(self.project_root)),
                                "proposito": f"Variable de configuración de screen en {nombre}",
                                "agente_asociado": nombre,
                            }
        return out

    # ------------------------------------------------------------
    # Generación / actualización del catálogo
    # ------------------------------------------------------------
    def generar_catalogo(self) -> dict:
        catalogo = {
            "agentes": self.catalogar_agentes(),
            "modulos": self.catalogar_modulos(),
            "aplicaciones": self.catalogar_aplicaciones(),
            "screens": self.catalogar_screens(),
            "ultima_actualizacion": _dt.datetime.now().isoformat(timespec="seconds"),
        }
        self._catalog = catalogo
        self._guardar(catalogo)
        return catalogo

    def actualizar_catalogo(self) -> dict:
        return self.generar_catalogo()

    def _guardar(self, catalogo: dict) -> None:
        tmp = self.catalog_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(catalogo, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.catalog_path)
        logger.info(f"Catálogo URA guardado: {self.catalog_path}")

    def cargar_catalogo(self) -> dict:
        if self.catalog_path.exists():
            try:
                self._catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Catálogo corrupto, reinicializando: {e}")
                self._catalog = {}
        return self._catalog

    # ------------------------------------------------------------
    # Consultas
    # ------------------------------------------------------------
    def buscar(self, termino: str) -> dict:
        if not self._catalog:
            self.cargar_catalogo()
        if not self._catalog:
            self.generar_catalogo()
        termino_l = termino.lower()
        resultados: dict[str, list[dict]] = {
            "agentes": [],
            "modulos": [],
            "aplicaciones": [],
            "screens": [],
        }
        for seccion in resultados:
            items = self._catalog.get(seccion, {})
            for nombre, datos in items.items():
                blob = (nombre + " " + json.dumps(datos, ensure_ascii=False)).lower()
                if termino_l in blob:
                    resultados[seccion].append({"nombre": nombre, **datos})
        return resultados

    def validar_coherencia(self) -> dict:
        if not self._catalog:
            self.cargar_catalogo()
        if not self._catalog:
            self.generar_catalogo()
        problemas: list[dict] = []
        # Cada agente debe tener archivo físico
        for nombre, datos in self._catalog.get("agentes", {}).items():
            ruta = self.project_root / datos.get("ruta", "")
            if not ruta.exists():
                problemas.append(
                    {"tipo": "archivo_inexistente", "nombre": nombre, "ruta_esperada": str(ruta)}
                )
            if datos.get("estado") == "roto":
                problemas.append(
                    {"tipo": "agente_roto", "nombre": nombre, "ruta": datos.get("ruta", "")}
                )
        # Detectar duplicados funcionales: misma intención + métodos solapados
        agentes = self._catalog.get("agentes", {})
        por_intencion: dict[str, list[str]] = {}
        for nombre, datos in agentes.items():
            por_intencion.setdefault(datos.get("intencion", "no_especificada"), []).append(nombre)
        duplicados: list[dict] = []
        for intencion, lista in por_intencion.items():
            if intencion in {"no_especificada", "asesoria_culinaria"}:
                continue
            if len(lista) > 1:
                duplicados.append({"intencion": intencion, "agentes": sorted(lista)})
        return {
            "problemas": problemas,
            "duplicados_funcionales": duplicados,
            "total_agentes": len(agentes),
            "total_modulos": len(self._catalog.get("modulos", {})),
        }


# Singleton ----------------------------------------------------------------
_documentador_instance: AgenteDocumentador | None = None


def get_agente_documentador() -> AgenteDocumentador:
    global _documentador_instance
    if _documentador_instance is None:
        _documentador_instance = AgenteDocumentador()
    return _documentador_instance


if __name__ == "__main__":  # pragma: no cover
    pass

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s - %(message)s")
    doc = AgenteDocumentador()
    cat = doc.generar_catalogo()
    print(f"Agentes catalogados:    {len(cat['agentes'])}")
    print(f"Módulos catalogados:    {len(cat['modulos'])}")
    print(f"Aplicaciones:           {len(cat['aplicaciones'])}")
    print(f"Screens:                {len(cat['screens'])}")
    print(f"Catálogo guardado en:   {doc.catalog_path}")
    val = doc.validar_coherencia()
    print(f"Problemas:              {len(val['problemas'])}")
    print(f"Duplicados funcionales: {len(val['duplicados_funcionales'])}")
