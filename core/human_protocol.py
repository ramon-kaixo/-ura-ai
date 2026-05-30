#!/usr/bin/env python3
"""
Protocolo Humano Virtual — Modo Sigilo
─────────────────────────────────────
Cuando un servicio bloquea automatización por DOM/HTML (bot detected),
URA cambia a imitación física: Chrome real del usuario, visión LLAVA,
ratón con curvas Bezier, escritura con fatiga humana.

Google ve a Ramón, no a un bot.
"""

import base64
import io
import math
import random
import subprocess
import time
from pathlib import Path

import pyautogui
import requests
from PIL import Image

# ── Config ──────────────────────────────────────────────────

OLLAMA = "http://localhost:11434"
VISION_MODEL = "llava:latest"
CHROME_PROFILE = Path.home() / "Library/Application Support/Google/Chrome"
SCREEN_W, SCREEN_H = pyautogui.size()

# Desactivar fail-safe para automatización (el ratón puede ir a esquinas)
pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.01  # Pausa mínima entre acciones


# ═══════════════════════════════════════════════════════════════
# MOVIMIENTO DE RATÓN HUMANO (Curvas Bezier)
# ═══════════════════════════════════════════════════════════════


def bezier_point(p0, p1, p2, p3, t):
    """Punto en curva Bezier cúbica en tiempo t [0,1]."""
    mt = 1 - t
    x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
    y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
    return (x, y)


def human_mouse_move(target_x: int, target_y: int, duration: float = None):
    """
    Mueve el ratón al destino con curva Bezier y velocidad variable.
    Simula un movimiento humano no robótico.
    """
    start_x, start_y = pyautogui.position()

    # Duración proporcional a la distancia (0.3–1.5 segundos)
    dist = math.hypot(target_x - start_x, target_y - start_y)
    if duration is None:
        duration = random.uniform(0.3, 1.2) * (dist / 800)

    # Puntos de control Bezier con variación aleatoria
    cp1_x = start_x + (target_x - start_x) * random.uniform(0.2, 0.4)
    cp1_y = start_y + (target_y - start_y) * random.uniform(0.1, 0.3) + random.randint(-80, 80)
    cp2_x = start_x + (target_x - start_x) * random.uniform(0.6, 0.8)
    cp2_y = start_y + (target_y - start_y) * random.uniform(0.7, 0.9) + random.randint(-60, 60)

    # Punto de "overshoot" — el humano a veces pasa de largo y corrige
    overshoot = random.random() < 0.08
    if overshoot:
        cp2_x += random.randint(-40, 40)
        cp2_y += random.randint(-40, 40)

    p0 = (start_x, start_y)
    p1 = (cp1_x, cp1_y)
    p2 = (cp2_x, cp2_y)
    p3 = (target_x, target_y)

    # Número de pasos: más pasos = movimiento más suave
    steps = max(15, int(dist / 6))
    for i in range(steps + 1):
        t = i / steps
        x, y = bezier_point(p0, p1, p2, p3, t)

        # Micro-pausas aleatorias (el humano no se mueve a velocidad constante)
        if random.random() < 0.02:
            time.sleep(random.uniform(0.003, 0.01))

        pyautogui.moveTo(x, y, duration=0)

    # Pequeño ajuste final (el humano rara vez acierta al centro exacto)
    time.sleep(random.uniform(0.02, 0.08))


def human_click(x: int, y: int, spread: int = 4):
    """
    Clic humano: ratón se mueve con curva, clic con offset aleatorio.
    """
    target_x = x + random.randint(-spread, spread)
    target_y = y + random.randint(-spread, spread)
    human_mouse_move(target_x, target_y)
    time.sleep(random.uniform(0.05, 0.2))
    pyautogui.click()
    time.sleep(random.uniform(0.1, 0.3))


def human_type(text: str):
    """
    Escritura con fatiga: carácter por carácter con retraso variable.
    """
    for char in text:
        pyautogui.write(char)
        # Retraso entre 50ms y 200ms (más lento en teclas difíciles)
        delay = random.uniform(0.05, 0.2)
        if char in '!@#$%^&*()_+{}|:"<>?':
            delay += 0.1  # Símbolos: más lento
        time.sleep(delay)


def human_scroll(amount: int):
    """Scroll con micro-pausas como un humano leyendo."""
    chunks = abs(amount) // 100
    direction = 1 if amount > 0 else -1
    for _ in range(max(1, chunks)):
        pyautogui.scroll(direction * random.randint(80, 120))
        time.sleep(random.uniform(0.05, 0.2))


# ═══════════════════════════════════════════════════════════════
# VISIÓN LLAVA — Encontrar elementos por imagen
# ═══════════════════════════════════════════════════════════════


def screenshot_b64() -> str:
    """Captura SOLO del area de contenido de Chrome en base64."""
    img = cropped_screenshot()
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


def ask_llava(prompt: str, temperature: float = 0.1) -> str:
    """Consulta a LLAVA sobre el contenido de Chrome."""
    img_b64 = screenshot_b64()
    resp = requests.post(
        f"{OLLAMA}/api/generate",
        json={
            "model": VISION_MODEL,
            "prompt": prompt,
            "images": [img_b64],
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=120,
    )
    data = resp.json()
    return data.get("response", "")


def find_coordinates(description: str, retries: int = 3) -> tuple[int, int] | None:
    """
    Pide a LLAVA que encuentre un elemento en Chrome y devuelva coordenadas absolutas.
    La coordenada Y ya incluye el offset de la barra de herramientas de Chrome.
    """
    import re

    # Resolución del area de contenido
    cw = CHROME_WIDTH
    ch = CHROME_HEIGHT - CONTENT_TOP

    prompt = f"""You are looking at a screenshot of Google Cloud Console at {cw}x{ch} resolution.
This is the CONTENT area only (browser tabs and URL bar are NOT shown).

Find the EXACT pixel coordinates of the element: "{description}"

Instructions:
1. Only if the element is clearly visible, respond with its CENTER pixel coordinates
2. Format: X,Y (just the numbers, nothing else)
3. X must be between 0 and {cw}
4. Y must be between 0 and {ch}
5. If the element is NOT clearly visible, respond with: NO"""

    for attempt in range(retries):
        answer = ask_llava(prompt).strip()
        matches = re.findall(r"(\d{2,4})\s*[,;]\s*(\d{2,4})", answer)
        if matches:
            x, y = int(matches[0][0]), int(matches[0][1])
            # Convertir de coordenadas de contenido a absolutas de pantalla
            abs_x = CHROME_LEFT + x
            abs_y = CHROME_TOP + CONTENT_TOP + y
            if 0 <= abs_x <= SCREEN_W and 0 <= abs_y <= SCREEN_H:
                return (abs_x, abs_y)

        if "NO" in answer.upper():
            if attempt < retries - 1:
                human_scroll(-200)
                time.sleep(1)
                continue
            return None

    return None


def find_text_ocr(text: str) -> tuple[int, int] | None:
    """
    OCR solo en el area de contenido de Chrome.
    Devuelve coordenadas absolutas de pantalla.
    """
    import pytesseract

    img = cropped_screenshot()
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)

    for i in range(len(data["text"])):
        t = data["text"][i].strip().lower()
        conf = int(data["conf"][i])
        if text.lower() in t and len(t) > 2 and conf >= 20:
            # Coordenadas relativas al area de contenido → absolutas
            x = CHROME_LEFT + data["left"][i] + data["width"][i] // 2
            y = CHROME_TOP + CONTENT_TOP + data["top"][i] + data["height"][i] // 2
            return (x, y)
    return None


def find_and_click(description: str) -> bool:
    """
    Intenta encontrar un elemento (primero LLAVA, luego OCR) y hace clic humano.
    """
    # 1. Intentar con LLAVA
    coords = find_coordinates(description)
    if coords:
        print(f"  [LLAVA] {description} → ({coords[0]}, {coords[1]})")
        human_click(coords[0], coords[1])
        return True

    # 2. Fallback con OCR
    coords = find_text_ocr(description)
    if coords:
        print(f"  [OCR] {description} → ({coords[0]}, {coords[1]})")
        human_click(coords[0], coords[1])
        return True

    print(f"  ~ {description}")
    return False


# ═══════════════════════════════════════════════════════════════
# NAVEGADOR REAL — Chrome con perfil de Ramón
# ═══════════════════════════════════════════════════════════════

# Posición y tamaño de Chrome ajustados para OCR fiable
CHROME_LEFT = 100
CHROME_TOP = 50
CHROME_WIDTH = 1400
CHROME_HEIGHT = 900
CONTENT_TOP = 200  # Debajo de tabs + URL bar


def setup_chrome_window():
    """Posiciona Chrome en coordenadas fijas para OCR fiable."""
    script = (
        'tell application "System Events"\n'
        '  tell process "Google Chrome"\n'
        f"    set position of front window to {{{CHROME_LEFT}, {CHROME_TOP}}}\n"
        f"    set size of front window to {{{CHROME_WIDTH}, {CHROME_HEIGHT}}}\n"
        "  end tell\n"
        "end tell"
    )
    subprocess.run(["osascript", "-e", script], capture_output=True)
    time.sleep(1)
    subprocess.run(["open", "-a", "Google Chrome"])
    time.sleep(1)
    pyautogui.hotkey("command", "0")  # Reset zoom
    time.sleep(0.5)


def cropped_screenshot() -> Image.Image:
    """Screenshot recortado SOLO al área de contenido de Chrome."""
    img = pyautogui.screenshot()
    return img.crop(
        (
            CHROME_LEFT,
            CHROME_TOP + CONTENT_TOP,
            CHROME_LEFT + CHROME_WIDTH,
            CHROME_TOP + CHROME_HEIGHT,
        )
    )


# ═══════════════════════════════════════════════════════════════
# DETECCIÓN DE BLOQUEO
# ═══════════════════════════════════════════════════════════════


class BotDetectedError(Exception):
    """Se detectó bloqueo anti-bot."""


def detect_block(page_text: str) -> bool:
    """Detecta si la página muestra un mensaje de bloqueo."""
    patterns = [
        "unusual traffic",
        "automated queries",
        "bot detected",
        "tráfico inusual",
        "consultas automatizadas",
        "robot",
        "captcha",
        "verify you are human",
        "verifica que eres humano",
        "403",
        "forbidden",
        "access denied",
    ]
    lower = page_text.lower()
    return any(p in lower for p in patterns)


# ═══════════════════════════════════════════════════════════════
# PROTOCOLO COMPLETO
# ═══════════════════════════════════════════════════════════════


class HumanProtocol:
    """
    Protocolo Humano Virtual completo.
    Uso:

        hp = HumanProtocol()
        hp.navigate("https://console.cloud.google.com/apis/credentials")
        hp.click_on("CREATE CREDENTIALS")
        hp.click_on("OAuth client ID")
        hp.type_into("Name", "URA")
        hp.click_on("CREATE")
        hp.click_on("DOWNLOAD JSON")
    """

    def __init__(self):
        self.attempts = 0
        self.max_retries = 3
        self.mode = "human"  # "code" | "human"

    def navigate(self, url: str):
        """Navega a una URL usando el Chrome real del usuario."""
        print(f"\n[Navegar] {url}")
        setup_chrome_window()
        subprocess.run(["open", url])
        time.sleep(5)

    def click_on(self, description: str) -> bool:
        """Encuentra y hace clic humano en un elemento por su descripción."""
        print(f"\n[Clic] '{description}'")
        self.attempts = 0

        while self.attempts < self.max_retries:
            if find_and_click(description):
                time.sleep(random.uniform(1.5, 3.0))
                return True
            self.attempts += 1
            print(f"     Reintento {self.attempts}/{self.max_retries}...")
            time.sleep(2)

        return False

    def type_into(self, field: str, text: str):
        """Encuentra un campo por descripción y escribe con fatiga humana."""
        print(f"\n[Escribir] '{text}' en '{field}'")
        if find_and_click(field):
            time.sleep(0.5)
            pyautogui.hotkey("command", "a")  # Seleccionar todo
            time.sleep(random.uniform(0.1, 0.3))
            human_type(text)
            time.sleep(0.5)
        else:
            print(f"  ~ Campo '{field}' no encontrado")

    def press_enter(self):
        """Presiona Enter con retraso humano."""
        time.sleep(random.uniform(0.1, 0.3))
        pyautogui.press("enter")

    def scroll_page(self, direction: str = "down", amount: int = 300):
        """Scroll humano."""
        sign = -1 if direction == "down" else 1
        human_scroll(sign * amount)


# ═══════════════════════════════════════════════════════════════
# PRUEBA
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("Protocolo Humano Virtual — Prueba de movimiento")
    print(f"Pantalla: {SCREEN_W}x{SCREEN_H}")

    # Demo: mover el ratón en curva
    print("\nMoviendo ratón con curva Bezier...")
    cx, cy = SCREEN_W // 2, SCREEN_H // 2
    human_mouse_move(cx, cy)
    print(f"Ratón en ({cx}, {cy})")

    print("\nProbando escritura humana...")
    human_type("Hola, soy URA.")
    print("Listo.")
