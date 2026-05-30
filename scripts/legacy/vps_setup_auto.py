#!/usr/bin/env python3
"""
URA configura el VPS de OVHcloud automáticamente.
Usa visión para ver la pantalla y GUI para hacer clics.
"""

import sys
import time
import subprocess
import os

sys.path.insert(0, "/Users/ramonesnaola/URA/ura_ia_1972")

from agents.agente_gui import GUIAgent
from agents.agente_vision import tomar_captura, analizar_imagen

gui = GUIAgent()
VPS_URL = "https://www.ovh.com/manager/#/vps/vps-57a71715.vps.ovh.net/dashboard"
PASSWORD = os.getenv("VPS_PASSWORD", "")


def paso(descripcion):
    print(f"  [{descripcion}]")
    time.sleep(2)


def ver_pantalla():
    """Saca captura y la describe con LLaVA."""
    ruta = tomar_captura()
    desc = analizar_imagen(ruta, "¿Qué ves en esta pantalla? Describe botones y campos.")
    print(f"    Pantalla: {desc}")
    return desc


def hacer_clic_en(texto_buscar, x_default=500, y_default=300):
    """Busca un texto en la pantalla y hace clic si aparece."""
    captura = tomar_captura()
    desc = analizar_imagen(
        captura, f"¿Aparece '{texto_buscar}' en pantalla? Responde SOLO 'sí' o 'no'."
    )
    if "sí" in desc.lower() or "si" in desc.lower():
        gui.click(x_default, y_default)
        print(f"    Clic en '{texto_buscar}'")
        return True
    else:
        print(f"    No se detecta '{texto_buscar}' aún.")
        return False


def main():
    print("🔧 URA configurando VPS de OVHcloud...")

    # 1. Abrir navegador en OVHcloud
    paso("Abriendo OVHcloud en navegador")
    subprocess.run(["open", VPS_URL])
    time.sleep(5)
    ver_pantalla()

    # 2. Iniciar sesión si hace falta
    paso("Verificando sesión")
    captura = tomar_captura()
    sesion = analizar_imagen(captura, "¿Pide usuario y contraseña? Responde 'login' o 'ok'.")
    if "login" in sesion.lower():
        gui.write("bt1025565-ovh")
        gui.press_key("tab")
        time.sleep(0.5)
        gui.write(PASSWORD)
        gui.press_key("return")
        time.sleep(3)
    ver_pantalla()

    # 3. Buscar "Sistema operativo" en menú
    paso("Buscando 'Sistema operativo'")
    hacer_clic_en("Sistema operativo", 200, 400)
    time.sleep(2)
    ver_pantalla()

    # 4. Reinstalar VPS
    paso("Pulsando 'Reinstalar mi VPS'")
    hacer_clic_en("Reinstalar", 400, 300)
    time.sleep(2)
    ver_pantalla()

    # 5. Seleccionar Ubuntu 24.04
    paso("Seleccionando Ubuntu 24.04")
    hacer_clic_en("Ubuntu 24", 300, 350)
    time.sleep(1)
    gui.press_key("return")
    time.sleep(2)
    ver_pantalla()

    # 6. Insertar cloud-init
    paso("Insertando cloud-init")
    hacer_clic_en("Datos de usuario", 400, 500)
    time.sleep(1)
    CLOUD_INIT = """#cloud-config
password: Ura2026Seguro!
chpasswd:
  expire: false
ssh_pwauth: true"""
    gui.write_multiline(CLOUD_INIT)
    time.sleep(1)
    gui.press_key("tab")
    gui.press_key("return")
    time.sleep(2)

    # 7. Confirmar
    paso("Confirmando reinstalación")
    hacer_clic_en("Confirmar", 600, 500)
    time.sleep(1)
    gui.press_key("return")
    time.sleep(5)

    print("✅ VPS configurado. Espera 3 minutos y conecta con:")
    print("   ssh ubuntu@146.59.229.191")
    print(f"   Contraseña: {PASSWORD}")


if __name__ == "__main__":
    main()
