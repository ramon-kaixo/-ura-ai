#!/usr/bin/env python3
"""ura_apple_control.py — Control total del Mac Mini via AppleScript
Permite a URA controlar volumen, brillo, teclado, raton, ventanas, y mas.
Se ejecuta como tool llamada por Open WebUI."""

import subprocess
import os


def osa(script):
    """Ejecuta AppleScript y devuelve resultado."""
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True, timeout=10)
    return r.stdout.strip()


def volumen(nivel=None):
    """Obtiene o establece el volumen (0-100)."""
    if nivel is not None:
        osa(f"set volume output volume {nivel}")
        return f"Volumen establecido a {nivel}"
    actual = osa("get volume settings")
    return actual


def volumen_subir():
    """Sube volumen 10 unidades."""
    actual = int(osa("output volume of (get volume settings)"))
    osa(f"set volume output volume {min(actual + 10, 100)}")
    return f"Volumen subido a {min(actual + 10, 100)}"


def volumen_bajar():
    """Baja volumen 10 unidades."""
    actual = int(osa("output volume of (get volume settings)"))
    osa(f"set volume output volume {max(actual - 10, 0)}")
    return f"Volumen bajado a {max(actual - 10, 0)}"


def mute():
    """Silencia/activa el volumen."""
    osa("set volume muted not (muted of (get volume settings))")
    muted = osa("muted of (get volume settings)")
    return "Volumen silenciado" if muted == "true" else "Volumen activado"


def brillo(nivel=None):
    """Obtiene o establece el brillo (0-100). En Mac modernos usa osascript."""
    if nivel is not None:
        osa(
            f'tell application "System Events" to set brightness of first display to {nivel / 100.0}'
        )
        return f"Brillo establecido a {nivel}%"
    try:
        r = subprocess.run(["brightness", "-l"], capture_output=True, text=True, timeout=5)
        return r.stdout.strip()
    except:
        return "Brillo: no se puede leer (necesita brightness CLI)"


def tecla(tecla):
    """Simula pulsacion de tecla. Ej: 'command', 'space', 'return', 'f11'."""
    osa(f'tell application "System Events" to key code {_keycode(tecla)}')
    return f"Tecla {tecla} pulsada"


def escribir(texto):
    """Escribe texto como si se tecleara."""
    # Escapar comillas
    texto = texto.replace('"', '\\"')
    osa(f'tell application "System Events" to keystroke "{texto}"')
    return f"Texto escrito: {texto[:50]}..."


def clic(x, y):
    """Hace clic en coordenadas x,y."""
    osa(f'tell application "System Events" to click at {{{x}, {y}}}')
    return f"Click en ({x}, {y})"


def raton_posicion():
    """Devuelve posicion actual del raton."""
    r = osa('tell application "System Events" to get position of mouse')
    return r


def capturar_pantalla(ruta=None):
    """Captura la pantalla actual."""
    if not ruta:
        ruta = os.path.expanduser("~/Desktop/ura_captura.png")
    subprocess.run(["screencapture", "-x", ruta], timeout=10)
    return f"Pantalla capturada en {ruta}"


def app_listar():
    """Lista aplicaciones abiertas."""
    r = osa(
        'tell application "System Events" to get name of every process whose background only is false'
    )
    return r


def app_abrir(nombre):
    """Abre una aplicacion."""
    osa(f'tell application "{nombre}" to activate')
    return f"Aplicacion {nombre} abierta"


def app_cerrar(nombre):
    """Cierra una aplicacion."""
    osa(f'tell application "{nombre}" to quit')
    return f"Aplicacion {nombre} cerrada"


def notificar(titulo, mensaje):
    """Muestra notificacion en macOS."""
    osa(f'display notification "{mensaje}" with title "{titulo}"')
    return f"Notificacion: {titulo} - {mensaje}"


def _keycode(tecla):
    """Convierte nombre de tecla a keycode."""
    mapa = {
        "return": 36,
        "enter": 36,
        "tab": 48,
        "space": 49,
        "delete": 51,
        "escape": 53,
        "command": 55,
        "shift": 56,
        "capslock": 57,
        "option": 58,
        "control": 59,
        "f1": 122,
        "f2": 120,
        "f3": 99,
        "f4": 118,
        "f5": 96,
        "f6": 97,
        "f7": 98,
        "f8": 100,
        "f9": 101,
        "f10": 109,
        "f11": 103,
        "f12": 111,
        "up": 126,
        "down": 125,
        "left": 123,
        "right": 124,
        "home": 115,
        "end": 119,
        "pageup": 116,
        "pagedown": 121,
    }
    return mapa.get(tecla.lower(), 0)


def main():
    import json
    import sys

    funciones = {
        "volumen": volumen,
        "volumen_subir": volumen_subir,
        "volumen_bajar": volumen_bajar,
        "mute": mute,
        "brillo": brillo,
        "tecla": tecla,
        "escribir": escribir,
        "clic": clic,
        "raton": raton_posicion,
        "capturar": capturar_pantalla,
        "apps": app_listar,
        "abrir": app_abrir,
        "cerrar": app_cerrar,
        "notificar": notificar,
    }
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        args = sys.argv[2:]
        if cmd in funciones:
            result = funciones[cmd](*args)
            print(json.dumps({"ok": True, "resultado": result}))
        else:
            print(json.dumps({"ok": False, "error": f"Comando desconocido: {cmd}"}))
    else:
        print(json.dumps({"ok": True, "comandos": list(funciones.keys())}))


if __name__ == "__main__":
    main()
