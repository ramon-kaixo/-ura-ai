#!/usr/bin/env python3
"""
agente_gui.py — URA Agente de Control GUI
==========================================
Permite a URA controlar la interfaz gráfica de macOS.

Capacidades:
- Clics de mouse (simple, doble, derecho)
- Escritura de texto
- Uso de AppleScript para apps nativas
- Screenshots para análisis
- Control de ventanas

Uso:
    from agente_gui import GUIAgent
    gui = GUIAgent()
    gui.click(100, 200)  # Clic en coordenadas
    gui.write("texto")
    gui.screenshot()  # Captura pantalla
"""

import logging

logger = logging.getLogger(__name__)
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(
    os.environ.get("URA_BASE_DIR", str(Path(__file__).resolve().parents[1]))
).expanduser()
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "agente_gui.log"


def log(msg, nivel="INFO"):
    linea = f"[{datetime.now().strftime('%H:%M:%S')}] [{nivel}] {msg}"
    print(linea)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(linea + "\n")
    except Exception as e:
        logger.warning(f"Error silencioso en agente_gui.log: {e}")
        # fallback: log ignorado


# ============================================================
# APPLE SCRIPT HELPERS
# ============================================================


def applescript(script: str) -> str:
    """Ejecuta AppleScript y devuelve el resultado."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            log(f"AppleScript error: {result.stderr}", "WARN")
            return f"Error: {result.stderr}"
    except Exception as e:
        return f"Exception: {e}"


# ============================================================
# AGENTE GUI
# ============================================================


class GUIAgent:
    """Agente para control de interfaz gráfica."""

    def __init__(self):
        self.screen_width, self.screen_height = self.get_screen_size()
        log(f"GUIAgent inicializado. Pantalla: {self.screen_width}x{self.screen_height}")

    def procesar(self, texto: str) -> str:
        """Procesar consulta para GUIAgent."""
        texto.lower()
        return "Puedo hacer clic, mover ratón y controlar interfaz. ¿Qué acción de GUI necesitas?"

    def ejecutar(self, texto: str) -> str:
        """Ejecutar acción para GUIAgent."""
        return self.procesar(texto)

    def consultar(self, texto: str) -> str:
        """Consultar información para GUIAgent."""
        return self.procesar(texto)

    def responder(self, texto: str) -> str:
        """Responder pregunta para GUIAgent."""
        return self.procesar(texto)

    def get_screen_size(self):
        """Obtiene el tamaño de la pantalla."""
        script = 'tell application "Finder" to get bounds of window of desktop'
        result = applescript(script)
        if "Error" in result:
            return 1920, 1080  # Default
        parts = result.split(",")
        if len(parts) == 4:
            return int(parts[2]), int(parts[3])
        return 1920, 1080

    # ============================================================
    # MOUSE
    # ============================================================

    def click(self, x: int = None, y: int = None, button: str = "left"):
        """Hace clic en coordenadas (o centro si no se especifica)."""
        if x is None or y is None:
            x, y = self.screen_width // 2, self.screen_height // 2

        script = f"""
tell application "System Events"
    set theMousePoint to point ({{{x}, {y}}})
    click theMousePoint
end tell
"""
        log(f"Clic en ({x}, {y})")
        return applescript(script)

    def double_click(self, x: int = None, y: int = None):
        """Doble clic en coordenadas."""
        if x is None or y is None:
            x, y = self.screen_width // 2, self.screen_height // 2

        script = f"""
tell application "System Events"
    set theMousePoint to point ({{{x}, {y}}})
    double click theMousePoint
end tell
"""
        log(f"Doble clic en ({x}, {y})")
        return applescript(script)

    def right_click(self, x: int = None, y: int = None):
        """Clic derecho en coordenadas."""
        if x is None or y is None:
            x, y = self.screen_width // 2, self.screen_height // 2

        script = f"""
tell application "System Events"
    set theMousePoint to point ({{{x}, {y}}})
    click theMousePoint using secondary button
end tell
"""
        log(f"Clic derecho en ({x}, {y})")
        return applescript(script)

    def move_to(self, x: int, y: int):
        """Mueve el mouse a coordenadas."""
        script = f"""
tell application "System Events"
    set theMousePoint to point ({{{x}, {y}}})
end tell
"""
        log(f"Mouse a ({x}, {y})")
        return applescript(script)

    # ============================================================
    # TECLADO
    # ============================================================

    def write(self, text: str, field_name: str = None):
        """
        Escribe texto.

        REGLA 5 - CONTRASEÑA FINAL: Detecta campos password y se detiene.

        Args:
            text: Texto a escribir
            field_name: Nombre del campo (opcional, para detectar si es password)
        """
        # Detectar si es un campo password
        if field_name:
            field_lower = field_name.lower()
            if "password" in field_lower or "pass" in field_lower or "pwd" in field_lower:
                log(
                    f"🚫 CAMPO PASSWORD DETECTADO: {field_name}. Por favor, introduzca la contraseña manualmente.",
                    "WARN",
                )
                raise ValueError(
                    f"Campo de password detectado ({field_name}). Por seguridad, URA no puede escribir en campos de password. Por favor, introduzca la contraseña manualmente."
                )

        # Detectar si el texto parece una contraseña (caracteres especiales comunes en passwords)
        # Solo si es un texto corto y complejo
        if len(text) < 50 and any(c in text for c in "!@#$%^&*()_+-=[]{}|;:,.<>?/~`"):
            log(
                "⚠️ Texto parece ser una contraseña. Por favor, verifique que no es un campo password.",
                "WARN",
            )

        escaped = text.replace('"', '\\"')
        script = f"""
tell application "System Events"
    keystroke "{escaped}"
end tell
"""
        log(f"Escribiendo: {text[:30]}...")
        return applescript(script)

    def write_multiline(self, text: str):
        """Escribe texto con saltos de línea usando portapapeles y Cmd+V."""
        try:
            # Copiar al portapapeles
            subprocess.run(["pbcopy"], input=text, text=True, check=True)
            log(f"Texto copiado al portapapeles: {len(text)} caracteres")

            # Pegar con Cmd+V
            self.press_shortcut("cmd", "v")
            log("Texto pegado con Cmd+V")
            return True
        except Exception as e:
            log(f"Error en write_multiline: {e}", "ERROR")
            return False

    def press_key(self, key: str):
        """Presiona una tecla (return, enter, tab, escape, etc)."""
        script = f"""
tell application "System Events"
    keystroke {key}
end tell
"""
        log(f"Tecla: {key}")
        return applescript(script)

    def press_shortcut(self, *keys):
        """Presiona atajo de teclado (cmd, shift, ctrl, alt)."""
        modifiers = []
        for k in keys[:-1]:
            if k.lower() in ["cmd", "command"]:
                modifiers.append("command down")
            elif k.lower() == "shift":
                modifiers.append("shift down")
            elif k.lower() == "ctrl":
                modifiers.append("control down")
            elif k.lower() == "alt":
                modifiers.append("option down")

        key = keys[-1]
        mod_str = ", ".join(modifiers)
        script = f"""
tell application "System Events"
    keystroke "{key}" using {{{mod_str}}}
end tell
"""
        log(f"Atajo: {'+'.join(keys)}")
        return applescript(script)

    # ============================================================
    # APLICACIONES
    # ============================================================

    def open_app(self, app_name: str):
        """Abre una aplicación."""
        escaped = app_name.replace('"', '\\"')
        script = f"""
tell application "{escaped}" to activate
"""
        log(f"Abrir app: {app_name}")
        return applescript(script)

    def close_app(self, app_name: str):
        """Cierra una aplicación."""
        escaped = app_name.replace('"', '\\"')
        script = f"""
tell application "{escaped}" to quit
"""
        log(f"Cerrar app: {app_name}")
        return applescript(script)

    def get_front_app(self) -> str:
        """Obtiene el nombre de la app en primer plano."""
        script = """
tell application "System Events"
    set frontApp to name of first process whose frontmost is true
end tell
"""
        result = applescript(script)
        if "Error" not in result:
            log(f"App en frente: {result}")
        return result

    # ============================================================
    # VENTANAS
    # ============================================================

    def get_windows(self, app_name: str = None):
        """Lista las ventanas de una app."""
        if app_name:
            script = f"""
tell application "{app_name}"
    set windowNames to name of windows
end tell
"""
        else:
            script = """
tell application "System Events"
    set appNames to name of every process whose visible is true
end tell
"""
        return applescript(script)

    def close_window(self, app_name: str):
        """Cierra la ventana activa."""
        return self.press_shortcut("cmd", "w")

    # ============================================================
    # SCREENSHOTS
    # ============================================================

    def screenshot(self, filename: str = None) -> str:
        """Toma screenshot y devuelve la ruta."""
        if filename is None:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"

        screenshots_dir = Path.home() / "Desktop"
        filepath = screenshots_dir / filename

        script = f"""
set theScreenshot to POSIX file "{filepath}"
set theClipboard to (read (theScreenshot) as JPEG picture)
"""
        applescript(script)

        # Alternativa más simple
        subprocess.run(["screencapture", str(filepath)], check=True)

        log(f"Screenshot guardado: {filepath}")
        return str(filepath)

    def screenshot_selection(self) -> str:
        """Permite selección de área para screenshot."""
        filename = f"screenshot_selection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        filepath = Path.home() / "Desktop" / filename

        subprocess.run(["screencapture", "-i", "-s", str(filepath)], check=True)

        if filepath.exists():
            log(f"Screenshot selección guardado: {filepath}")
            return str(filepath)
        return "Cancelado"

    # ============================================================
    # UTILIDADES
    # ============================================================

    def announce(self, message: str):
        """Anuncia texto con VoiceOver."""
        escaped = message.replace('"', '\\"')
        script = f"""
say "{escaped}"
"""
        log(f"Anunciar: {message}")
        return applescript(script)

    def notification(self, title: str, message: str):
        """Muestra notificación del sistema."""
        escaped_title = title.replace('"', '\\"')
        escaped_msg = message.replace('"', '\\"')
        script = f"""
display notification "{escaped_msg}" with title "{escaped_title}"
"""
        log(f"Notificación: {title}")
        return applescript(script)

    def open_url(self, url: str):
        """Abre URL en navegador default."""
        script = f"""
tell application "Safari"
    open location "{url}"
    activate
end tell
"""
        log(f"Abrir URL: {url}")
        return applescript(script)

    def search_spotlight(self, query: str):
        """Busca con Spotlight (Cmd+Espacio)."""
        self.press_shortcut("cmd", "space")
        time.sleep(0.3)
        self.write(query)
        time.sleep(0.3)
        self.press_key("return")


# ============================================================
# SHORTCUT
# ============================================================

_gui = None


def get_gui() -> GUIAgent:
    global _gui
    if _gui is None:
        _gui = GUIAgent()
    return _gui


# ============================================================
# CLI
# ============================================================

if __name__ == "__main__":
    import sys

    gui = GUIAgent()

    if len(sys.argv) < 2:
        print("Agente GUI de URA")
        print("Uso: python3 agente_gui.py <comando> [args]")
        print("")
        print("Comandos:")
        print("  click x y          - Clic en coordenadas")
        print("  write <texto>      - Escribe texto")
        print("  open <app>         - Abre aplicación")
        print("  screenshot         - Toma screenshot")
        print("  notify <titulo> <msg> - Muestra notificación")
        print("  front              - Muestra app en frente")
        print("  spotlight <query>  - Busca con Spotlight")
        sys.exit(0)

    cmd = sys.argv[1]

    if cmd == "click" and len(sys.argv) >= 4:
        x, y = int(sys.argv[2]), int(sys.argv[3])
        print(gui.click(x, y))
    elif cmd == "write" and len(sys.argv) >= 3:
        print(gui.write(" ".join(sys.argv[2:])))
    elif cmd == "open" and len(sys.argv) >= 3:
        print(gui.open_app(sys.argv[2]))
    elif cmd == "screenshot":
        print(gui.screenshot())
    elif cmd == "notify" and len(sys.argv) >= 4:
        print(gui.notification(sys.argv[2], " ".join(sys.argv[3:])))
    elif cmd == "front":
        print(gui.get_front_app())
    elif cmd == "spotlight" and len(sys.argv) >= 3:
        print(gui.search_spotlight(" ".join(sys.argv[2:])))
    else:
        print(f"Comando desconocido: {cmd}")
