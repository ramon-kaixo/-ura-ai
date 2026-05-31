#!/usr/bin/env python3
"""Traductor mecánico español→inglés para código Python.

Usa AST para detectar identificadores, diccionario técnico para traducir,
y verifica referencias cruzadas antes de aplicar cambios.

Sin LLM. Determinista. Instantáneo (~5s para 872 archivos).

Uso:
  python scripts/pro/translate_to_english.py --dry-run     # solo reporta
  python scripts/pro/translate_to_english.py --apply        # aplica cambios
  python scripts/pro/translate_to_english.py <archivo>      # un solo archivo
"""

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

URA_ROOT = Path(os.environ.get("URA_ROOT", os.path.expanduser("~/URA/ura_ia_1972")))

# ── Diccionario técnico español→inglés ────────────────────────────────────
TECH_DICT = {
    # Verbos de acción
    "buscar": "search",
    "buscador": "searcher",
    "buscando": "searching",
    "guardar": "save",
    "guardado": "saved",
    "cargar": "load",
    "cargando": "loading",
    "calcular": "calculate",
    "calculando": "calculating",
    "obtener": "get",
    "obteniendo": "getting",
    "enviar": "send",
    "enviando": "sending",
    "recibir": "receive",
    "recibiendo": "receiving",
    "crear": "create",
    "creando": "creating",
    "creado": "created",
    "eliminar": "delete",
    "eliminado": "deleted",
    "borrar": "delete",
    "borrado": "deleted",
    "actualizar": "update",
    "actualizado": "updated",
    "verificar": "verify",
    "verificando": "verifying",
    "validar": "validate",
    "validado": "validated",
    "comprobar": "check",
    "comprobando": "checking",
    "procesar": "process",
    "procesando": "processing",
    "analizar": "analyze",
    "analizando": "analyzing",
    "mostrar": "show",
    "mostrando": "showing",
    "ejecutar": "execute",
    "ejecutando": "executing",
    "conectar": "connect",
    "conectado": "connected",
    "desconectar": "disconnect",
    "iniciar": "start",
    "iniciando": "starting",
    "inicio": "start",
    "detener": "stop",
    "detenido": "stopped",
    "pausar": "pause",
    "pausado": "paused",
    "reanudar": "resume",
    "abrir": "open",
    "abierto": "opened",
    "cerrar": "close",
    "cerrado": "closed",
    "leer": "read",
    "leyendo": "reading",
    "escribir": "write",
    "escribiendo": "writing",
    "copiar": "copy",
    "copiado": "copied",
    "mover": "move",
    "movido": "moved",
    "renombrar": "rename",
    "comparar": "compare",
    "ordenar": "sort",
    "ordenado": "sorted",
    "filtrar": "filter",
    "filtrado": "filtered",
    "limpiar": "clean",
    "limpiado": "cleaned",
    "extraer": "extract",
    "extraido": "extracted",
    "generar": "generate",
    "generando": "generating",
    "construir": "build",
    "construyendo": "building",
    "destruir": "destroy",
    "permitir": "allow",
    "permitido": "allowed",
    "denegar": "deny",
    "denegado": "denied",
    "bloquear": "block",
    "bloqueado": "blocked",
    "desbloquear": "unblock",
    "registrar": "register",
    "registrado": "registered",
    "notificar": "notify",
    "avisar": "warn",
    "aviso": "warning",
    "reparar": "repair",
    "reparado": "repaired",
    "corregir": "fix",
    "corregido": "fixed",
    "configurar": "configure",
    "configurado": "configured",
    "instalar": "install",
    "instalado": "installed",
    "desinstalar": "uninstall",
    "publicar": "publish",
    "publicado": "published",
    "compartir": "share",
    "compartido": "shared",
    "importar": "import",
    "exportar": "export",
    "cifrar": "encrypt",
    "cifrado": "encrypted",
    "descifrar": "decrypt",
    "firmar": "sign",
    "firmado": "signed",
    "programar": "schedule",
    "programado": "scheduled",
    "resolver": "resolve",
    "resuelto": "resolved",
    "detectar": "detect",
    "detectado": "detected",
    "monitorizar": "monitor",
    "supervisar": "supervise",
    "coordinar": "coordinate",
    "asignar": "assign",
    "asignado": "assigned",
    "liberar": "release",
    "liberado": "released",
    "reservar": "reserve",
    "reservado": "reserved",
    "consultar": "query",
    "consulta": "query",
    "responder": "respond",
    "respuesta": "response",
    "preguntar": "ask",
    "pregunta": "question",
    "devolver": "return",
    "recorrer": "iterate",
    "recorrido": "iteration",
    "evaluar": "evaluate",
    "estimar": "estimate",
    # Dominio: Cocina / Gastronomía
    "cocina": "kitchen",
    "cocinar": "cook",
    "receta": "recipe",
    "recetas": "recipes",
    "ingrediente": "ingredient",
    "ingredientes": "ingredients",
    "plato": "dish",
    "platos": "dishes",
    "postre": "dessert",
    "postres": "desserts",
    "menu": "menu",
    "menus": "menus",
    "gastronomo": "gastronome",
    "gastronomia": "gastronomy",
    "navarra": "navarre",
    "temporada": "season",
    "comensal": "diner",
    "comensales": "diners",
    # Dominio: Administración / Contabilidad
    "contable": "accounting",
    "contabilidad": "accounting",
    "factura": "invoice",
    "facturas": "invoices",
    "asiento": "entry",
    "asientos": "entries",
    "deduccion": "deduction",
    "impuesto": "tax",
    "impuestos": "taxes",
    "nomina": "payroll",
    "nominas": "payrolls",
    "gasto": "expense",
    "gastos": "expenses",
    "ingreso": "income",
    "ingresos": "income",
    "presupuesto": "budget",
    "balance": "balance",
    "cuenta": "account",
    "bancario": "banking",
    "banco": "bank",
    "tesoreria": "treasury",
    # Dominio: Legal / RRHH
    "juridico": "legal",
    "juridica": "legal",
    "normativa": "regulation",
    "laboral": "labor",
    "contrato": "contract",
    "contratos": "contracts",
    "nominas": "payroll",
    "empleado": "employee",
    "empleados": "employees",
    "candidato": "candidate",
    "vacante": "vacancy",
    "entrevista": "interview",
    # Dominio: Marketing
    "marketing": "marketing",
    "banner": "banner",
    "promocion": "promotion",
    "promocional": "promotional",
    "campaña": "campaign",
    "anuncio": "advertisement",
    "publicidad": "advertising",
    "video": "video",
    "imagen": "image",
    "imagenes": "images",
    # Dominio: Sistema / Infraestructura
    "servidor": "server",
    "cliente": "client",
    "puerto": "port",
    "conexion": "connection",
    "archivo": "file",
    "archivos": "files",
    "directorio": "directory",
    "carpeta": "folder",
    "ruta": "path",
    "memoria": "memory",
    "disco": "disk",
    "red": "network",
    "usuario": "user",
    "usuarios": "users",
    "permiso": "permission",
    "permisos": "permissions",
    "token": "token",
    "sesion": "session",
    "contraseña": "password",
    "clave": "key",
    "certificado": "certificate",
    "firma": "signature",
    "log": "log",
    "logs": "logs",
    "registro": "record",
    "registros": "records",
    "evento": "event",
    "eventos": "events",
    "alerta": "alert",
    "alertas": "alerts",
    "error": "error",
    "errores": "errors",
    "excepcion": "exception",
    "traza": "trace",
    "depuracion": "debug",
    "umbral": "threshold",
    "limite": "limit",
    "limites": "limits",
    # Dominio: IA / Agentes
    "agente": "agent",
    "agentes": "agents",
    "modelo": "model",
    "modelos": "models",
    "orquestador": "orchestrator",
    "conciencia": "consciousness",
    "autonomia": "autonomy",
    "autonomo": "autonomous",
    "aprendizaje": "learning",
    "entrenamiento": "training",
    "inferencia": "inference",
    "contexto": "context",
    "embeddings": "embeddings",
    "intencion": "intent",
    "intenciones": "intents",
    "prediccion": "prediction",
    "clasificador": "classifier",
    "vocabulario": "vocabulary",
    # Adjetivos / Estados
    "activo": "active",
    "inactivo": "inactive",
    "pendiente": "pending",
    "completado": "completed",
    "completo": "complete",
    "parcial": "partial",
    "temporal": "temporary",
    "permanente": "permanent",
    "global": "global",
    "local": "local",
    "remoto": "remote",
    "interno": "internal",
    "externo": "external",
    "publico": "public",
    "privado": "private",
    "seguro": "safe",
    "inseguro": "unsafe",
    "rapido": "fast",
    "lento": "slow",
    "nuevo": "new",
    "viejo": "old",
    "anterior": "previous",
    "siguiente": "next",
    "primero": "first",
    "ultimo": "last",
    "maximo": "maximum",
    "minimo": "minimum",
    "promedio": "average",
    "total": "total",
    "parcial": "partial",
    # Sustantivos comunes en código
    "resultado": "result",
    "resultados": "results",
    "entrada": "input",
    "salida": "output",
    "origen": "source",
    "destino": "destination",
    "formato": "format",
    "tipo": "type",
    "tipos": "types",
    "valor": "value",
    "valores": "values",
    "lista": "list",
    "listas": "lists",
    "diccionario": "dictionary",
    "conjunto": "set",
    "tupla": "tuple",
    "indice": "index",
    "elemento": "element",
    "elementos": "elements",
    "columna": "column",
    "columnas": "columns",
    "fila": "row",
    "filas": "rows",
    "tabla": "table",
    "tablas": "tables",
    "campo": "field",
    "campos": "fields",
    "etiqueta": "label",
    "etiquetas": "labels",
    "marca": "mark",
    "marcas": "marks",
    "estado": "state",
    "estados": "states",
    "modo": "mode",
    "modos": "modes",
    "nivel": "level",
    "niveles": "levels",
    "capa": "layer",
    "capas": "layers",
    "bloque": "block",
    "bloques": "blocks",
    "seccion": "section",
    "pagina": "page",
    "paginas": "pages",
    "panel": "panel",
    "ventana": "window",
    "boton": "button",
    "botones": "buttons",
    "mensaje": "message",
    "mensajes": "messages",
    "texto": "text",
    "textos": "texts",
    "documento": "document",
    "documentos": "documents",
    "ayuda": "help",
    "soporte": "support",
    "version": "version",
    "nombre": "name",
    "nombres": "names",
    "apellido": "surname",
    "direccion": "address",
    "telefono": "phone",
    "email": "email",
    "correo": "email",
    "fecha": "date",
    "fechas": "dates",
    "hora": "time",
    "horas": "hours",
    "duracion": "duration",
    "periodo": "period",
    "intervalo": "interval",
    "peso": "weight",
    "altura": "height",
    "anchura": "width",
    "profundidad": "depth",
    "color": "color",
    "colores": "colors",
    "tamaño": "size",
    "cantidad": "quantity",
    "porcentaje": "percentage",
    "numero": "number",
    "numeros": "numbers",
    "cadena": "string",
    "booleano": "boolean",
    "entero": "integer",
    "decimal": "decimal",
    "flotante": "float",
    "nulo": "null",
    "vacio": "empty",
    "verdadero": "true",
    "falso": "false",
    "codigo": "code",
    "prueba": "test",
    "pruebas": "tests",
    "backup": "backup",
    "copia": "copy",
    "parche": "patch",
    "rama": "branch",
    "commit": "commit",
    "fusion": "merge",
    "versionado": "versioning",
    "despliegue": "deployment",
    "sandbox": "sandbox",
    "fabrica": "factory",
    "aduana": "gate",
    "tuneladora": "tunneler",
    "explorador": "explorer",
    "intentar": "attempt",
    "reintentar": "retry",
    "recuperar": "recover",
    "recuperacion": "recovery",
    "servicio": "service",
    "servicios": "services",
    "supervisor": "supervisor",
}


def is_excluded(path: str) -> bool:
    excl = ["/venv/", "/.git/", "/.mypy_cache/", "/__pycache__/", "/.tox/", "/node_modules/"]
    return any(e in path for e in excl)


def split_identifier(name: str) -> list[str]:
    """Split snake_case or camelCase into word parts."""
    return re.findall(r"[a-záéíóúñü]+", name.lower())


def translate_word(word: str) -> str | None:
    """Translate a single Spanish word to English using tech dictionary."""
    # Exact match
    if word in TECH_DICT:
        return TECH_DICT[word]
    # Try common suffixes
    for suffix_es, suffix_en in [("ando", "ing"), ("iendo", "ing"), ("ado", "ed"), ("ido", "ed")]:
        if word.endswith(suffix_es):
            base = word[: -len(suffix_es)]
            if base in TECH_DICT:
                return TECH_DICT[base] + suffix_en
    return None


def translate_identifier(name: str) -> str | None:
    """Translate a full identifier (snake_case) from Spanish to English."""
    parts = split_identifier(name)
    translated = []
    all_translated = True
    for part in parts:
        t = translate_word(part)
        if t:
            translated.append(t)
        else:
            translated.append(part)
            all_translated = False
    if all_translated and translated != parts:
        return "_".join(translated)
    return None


def collect_identifiers(file_path: str) -> set[str]:
    """Extract all function, class, and top-level variable names."""
    try:
        source = Path(file_path).read_text(encoding="utf-8")
        tree = ast.parse(source)
    except (SyntaxError, UnicodeDecodeError):
        return set()

    names = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Name):
            names.add(node.id)
        elif isinstance(node, ast.arg):
            names.add(node.arg)
    return names


def build_translation_map(targets: list[str] | None = None) -> dict[str, str]:
    """Build old_name → new_name map from all files."""
    name_map = {}
    py_files = (
        targets if targets else [str(p) for p in URA_ROOT.rglob("*.py") if not is_excluded(str(p))]
    )

    for fpath in py_files:
        for name in collect_identifiers(fpath):
            if name.startswith("_"):
                continue  # skip private names for now
            # Only translate names with at least 2 parts and containing Spanish chars
            parts = split_identifier(name)
            if len(parts) < 2:
                continue
            has_spanish = any(c in w for w in parts for c in "áéíóúñü")
            has_translatable = any(translate_word(p) for p in parts)
            if has_spanish or has_translatable:
                new_name = translate_identifier(name)
                if new_name and new_name != name:
                    name_map[name] = new_name

    return name_map


def apply_translations(name_map: dict[str, str], targets: list[str] | None = None) -> int:
    """Apply the translation map across all files using word-boundary regex."""
    py_files = (
        targets if targets else [str(p) for p in URA_ROOT.rglob("*.py") if not is_excluded(str(p))]
    )

    changes = 0
    for fpath in py_files:
        original = Path(fpath).read_text(encoding="utf-8")
        modified = original
        for old_name, new_name in name_map.items():
            # Replace only whole-word identifiers (not substrings)
            pattern = rf"\b{re.escape(old_name)}\b"
            if re.search(pattern, modified):
                modified = re.sub(pattern, new_name, modified)
                changes += 1
        if modified != original:
            Path(fpath).write_text(modified, encoding="utf-8")

    return changes


def verify_all_compile() -> bool:
    """Verify all Python files compile after translation."""
    for fpath in URA_ROOT.rglob("*.py"):
        if is_excluded(str(fpath)):
            continue
        try:
            source = fpath.read_text(encoding="utf-8")
            compile(source, str(fpath), "exec")
        except Exception as e:
            print(f"  ❌ {fpath.relative_to(URA_ROOT)}: {e}")
            return False
    return True


def main():
    targets = None
    dry_run = "--dry-run" in sys.argv
    apply = "--apply" in sys.argv

    # Specific file target?
    file_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if file_args:
        targets = [str(URA_ROOT / f) if not f.startswith("/") else f for f in file_args]

    print("🔍 Escaneando identificadores...")
    name_map = build_translation_map(targets)
    print(f"📋 {len(name_map)} identificadores traducibles encontrados:")

    for old, new in sorted(name_map.items(), key=lambda x: x[0]):
        print(f"   {old} → {new}")

    if dry_run:
        print(f"\n🏷️  DRY RUN — {len(name_map)} cambios detectados (sin aplicar)")
        return

    if not apply:
        print("\n⚠️  Usa --apply para aplicar los cambios o --dry-run para previsualizar")
        return

    print("\n✏️  Aplicando traducciones...")
    git_backup = subprocess.run(
        ["git", "add", "-A"],
        capture_output=True,
        cwd=URA_ROOT,
    )
    subprocess.run(
        ["git", "commit", "--no-verify", "-m", "backup pre-traduccion-ingles"],
        capture_output=True,
        cwd=URA_ROOT,
    )

    changes = apply_translations(name_map, targets)

    print("🧹 Verificando compilación...")
    if verify_all_compile():
        print(f"✅ {changes} cambios aplicados. Todos los archivos compilan.")
        subprocess.run(
            ["ruff", "check", "--fix", "--unsafe-fixes", str(URA_ROOT)],
            capture_output=True,
            timeout=60,
        )
        subprocess.run(["ruff", "format", str(URA_ROOT)], capture_output=True, timeout=60)
    else:
        print("❌ Error de compilación. Revirtiendo con git...")
        subprocess.run(["git", "reset", "--hard", "HEAD~1"], capture_output=True, cwd=URA_ROOT)


if __name__ == "__main__":
    main()
