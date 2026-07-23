#!/usr/bin/env python3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

AGENTES_DIR = Path("~/URA/ura_ia_1972/agents/").expanduser()
OUTPUT_DIR = Path("~/Desktop/").expanduser()
TELEGRAM_SCRIPT = "/opt/ura/scripts/telegram_notify.sh"


def verificar_agente(ruta_agente):
    """Verifica un agente usando subprocess para evitar import side effects."""
    nombre = ruta_agente.name
    resultado = {
        "nombre": nombre,
        "estado": "❌ ROTO",
        "errores": [],
        "funciones": [],
        "arreglado": False,
    }

    # Ignorar __init__.py
    if nombre == "__init__.py":
        resultado["estado"] = "⚠️ PARCIAL"
        return resultado

    try:
        # Verificar sintaxis con python -m py_compile
        result = subprocess.run(
            ["python3", "-m", "py_compile", str(ruta_agente)],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode != 0:
            resultado["errores"].append(f"Error de sintaxis: {result.stderr}")
            return resultado

        # Extraer funciones usando ast
        result = subprocess.run(
            [
                "python3",
                "-c",
                f"import ast; tree = ast.parse(open('{ruta_agente}').read()); print([n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and not n.name.startswith('_')])",
            ],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )

        if result.returncode == 0:
            try:
                funciones = eval(result.stdout.strip())  # noqa: S307
                resultado["funciones"] = funciones
                if len(funciones) > 0:
                    resultado["estado"] = "✅ FUNCIONA"
                else:
                    resultado["estado"] = "⚠️ PARCIAL"
                    resultado["errores"].append("No se encontraron funciones públicas")
            except:  # noqa: E722
                resultado["estado"] = "⚠️ PARCIAL"
        else:
            resultado["estado"] = "⚠️ PARCIAL"
            resultado["errores"].append(f"No se pudieron extraer funciones: {result.stderr}")

    except subprocess.TimeoutExpired:
        resultado["errores"].append("Timeout al verificar")
    except Exception as e:
        resultado["errores"].append(f"Error general: {e}")

    return resultado


def generar_informe(resultados):
    """Genera el informe en formato Markdown."""
    fecha = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    ruta_informe = OUTPUT_DIR / f"VERIFICACION_AGENTES_{fecha}.md"

    contenido = "# Verificación de Agentes URA\n"
    contenido += f"**Fecha:** {datetime.now(UTC).strftime('%Y-%m-%d %H:%M:%S')}\n"
    contenido += f"**Total agentes:** {len(resultados)}\n\n"

    # Resumen
    funcionando = sum(1 for r in resultados if "FUNCIONA" in r["estado"])
    parcial = sum(1 for r in resultados if "PARCIAL" in r["estado"])
    rotos = sum(1 for r in resultados if "ROTO" in r["estado"])

    contenido += "## Resumen\n"
    contenido += f"- ✅ Funcionando: {funcionando}\n"
    contenido += f"- ⚠️ Parcial: {parcial}\n"
    contenido += f"- ❌ Rotos: {rotos}\n\n"

    # Detalles
    contenido += "## Detalles por Agente\n\n"
    for resultado in resultados:
        contenido += f"### {resultado['nombre']}\n"
        contenido += f"**Estado:** {resultado['estado']}\n"
        if resultado["funciones"]:
            contenido += f"**Funciones:** {', '.join(resultado['funciones'][:5])}\n"
        if resultado["errores"]:
            contenido += "**Errores:**\n"
            for error in resultado["errores"]:
                contenido += f"  - {error}\n"
        contenido += "\n"

    ruta_informe.write_text(contenido)
    return ruta_informe


def enviar_telegram(mensaje) -> bool:
    """Envía notificación por Telegram."""
    try:
        if Path(TELEGRAM_SCRIPT).exists():
            subprocess.run([TELEGRAM_SCRIPT, mensaje], check=True, capture_output=True)
            return True
    except Exception:  # noqa: S110
        pass
    return False


def main() -> None:
    # Obtener todos los archivos Python
    agentes = list(AGENTES_DIR.glob("*.py"))

    resultados = []
    for agente in agentes:
        resultado = verificar_agente(agente)
        resultados.append(resultado)

    # Generar informe
    generar_informe(resultados)

    # Resumen para Telegram
    funcionando = sum(1 for r in resultados if "FUNCIONA" in r["estado"])
    parcial = sum(1 for r in resultados if "PARCIAL" in r["estado"])
    rotos = sum(1 for r in resultados if "ROTO" in r["estado"])

    mensaje = "🤖 Verificación Agentes URA\n"
    mensaje += f"Total: {len(resultados)} | ✅ {funcionando} | ⚠️ {parcial} | ❌ {rotos}"

    enviar_telegram(mensaje)


if __name__ == "__main__":
    main()
