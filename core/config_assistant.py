#!/usr/bin/env python3
"""
core/config_assistant.py - Asistente de Configuración Guiado
Guía al usuario paso a paso para configurar Telegram y Gmail
"""

import logging
import webbrowser
from pathlib import Path

logger = logging.getLogger(__name__)

# Rutas de configuración
CONFIG_PATH = Path(__file__).parent.parent / "config"


class ConfigAssistant:
    """Asistente de configuración guiado"""

    def __init__(self):
        self.config_path = CONFIG_PATH

    def telegram_setup(self):
        """Asistente de configuración de Telegram"""
        print("\n" + "=" * 70)
        print("📱 ASISTENTE DE CONFIGURACIÓN - TELEGRAM")
        print("=" * 70)

        print("\n🔧 PASO 1: Obtener API ID y API Hash")
        print("-" * 70)
        print("1. Vamos a abrir my.telegram.org en tu navegador")
        print("2. Inicia sesión con tu número de teléfono")
        print("3. Ve a 'API development tools'")
        print("4. Crea una nueva aplicación:")
        print("   - App title: URA Assistant")
        print("   - Short name: ura_assistant")
        print("   - Platform: Desktop")
        print("   - Description: Personal assistant")
        print("5. Copia el API ID y API Hash que te dan")
        print("\n👉 Pulsa ENTER para abrir my.telegram.org...")
        input()

        # Abrir my.telegram.org
        webbrowser.open("https://my.telegram.org")

        print("\n🔧 PASO 2: Introduce tus credenciales")
        print("-" * 70)
        api_id = input("👉 API ID: ").strip()
        api_hash = input("👉 API Hash: ").strip()
        phone = input("👉 Tu número de teléfono (con +34): ").strip()

        # Guardar configuración
        config = {"api_id": int(api_id), "api_hash": api_hash, "phone": phone}

        import json

        config_file = self.config_path / "telegram_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ Configuración guardada en: {config_file}")
        print("🎉 Telegram configurado correctamente")
        print("=" * 70 + "\n")

    def gmail_setup(self):
        """Asistente de configuración de Gmail"""
        print("\n" + "=" * 70)
        print("📧 ASISTENTE DE CONFIGURACIÓN - GMAIL")
        print("=" * 70)

        print("\n🔧 PASO 1: Crear proyecto en Google Cloud Console")
        print("-" * 70)
        print("1. Vamos a abrir Google Cloud Console en tu navegador")
        print("2. Crea un nuevo proyecto:")
        print("   - Nombre: URA Assistant")
        print("   - Organización: (tu cuenta personal)")
        print("3. Espera a que se cree el proyecto")
        print("\n👉 Pulsa ENTER para abrir Google Cloud Console...")
        input()

        # Abrir Google Cloud Console
        webbrowser.open("https://console.cloud.google.com")

        print("\n🔧 PASO 2: Habilitar Gmail API")
        print("-" * 70)
        print("1. En el menú, busca 'APIs & Services' > 'Library'")
        print("2. Busca 'Gmail API'")
        print("3. Haz clic en 'Gmail API'")
        print("4. Haz clic en 'Enable'")
        print("5. Espera a que se habilite la API")
        print("\n👉 Pulsa ENTER cuando hayas habilitado la API...")
        input()

        print("\n🔧 PASO 3: Crear credenciales OAuth 2.0")
        print("-" * 70)
        print("1. Ve a 'APIs & Services' > 'Credentials'")
        print("2. Haz clic en 'Create Credentials'")
        print("3. Selecciona 'OAuth client ID'")
        print("4. Si te pide configurar consent screen:")
        print("   - User Type: External")
        print("   - App name: URA Assistant")
        print("   - User support email: tu email")
        print("   - Developer contact: tu email")
        print("   - Skip 'Scopes' (no añadir scopes todavía)")
        print("   - Test users: añade tu email")
        print("5. Para OAuth client ID:")
        print("   - Application type: Desktop application")
        print("   - Name: URA Assistant Desktop")
        print("6. Descarga el archivo JSON (credentials.json)")
        print("\n👉 Pulsa ENTER cuando hayas descargado credentials.json...")
        input()

        print("\n🔧 PASO 4: Copiar credentials.json")
        print("-" * 70)
        print("1. Copia el archivo credentials.json que descargaste")
        print(f"2. Pégalo en: {self.config_path}")
        print("3. Renómbralo a: gmail_credentials.json")
        print("\n👉 Pulsa ENTER cuando hayas copiado el archivo...")
        input()

        # Verificar que el archivo existe
        credentials_file = self.config_path / "gmail_credentials.json"
        if credentials_file.exists():
            print(f"\n✅ credentials.json encontrado en: {credentials_file}")
            print("🎉 Gmail configurado correctamente")
        else:
            print(f"\n❌ No se encontró credentials.json en: {credentials_file}")
            print("⚠️ Por favor, copia el archivo manualmente")

        print("=" * 70 + "\n")

    def instagram_setup(self):
        """Asistente de configuración de Instagram"""
        print("\n" + "=" * 70)
        print("📷 ASISTENTE DE CONFIGURACIÓN - INSTAGRAM")
        print("=" * 70)

        print("\n🔧 PASO 1: Introduce tus credenciales")
        print("-" * 70)
        username = input("👉 Usuario de Instagram: ").strip()
        password = input("👉 Contraseña de Instagram: ").strip()

        # Guardar configuración
        config = {"username": username, "password": password}

        import json

        config_file = self.config_path / "instagram_config.json"
        with open(config_file, "w") as f:
            json.dump(config, f, indent=2)

        print(f"\n✅ Configuración guardada en: {config_file}")
        print("🎉 Instagram configurado correctamente")
        print("=" * 70 + "\n")

    def full_setup(self):
        """Ejecutar asistente de configuración completo"""
        print("\n" + "=" * 70)
        print("🚀 ASISTENTE DE CONFIGURACIÓN COMPLETO - URA")
        print("=" * 70)
        print("\nEste asistente te guiará paso a paso para configurar:")
        print("📱 Telegram")
        print("📧 Gmail")
        print("📷 Instagram")
        print("\n⚠️ WhatsApp ya está configurado (escanea QR al usar)")
        print("=" * 70)

        print("\n👉 ¿Quieres configurar Telegram? (s/n): ", end="")
        if input().lower() == "s":
            self.telegram_setup()

        print("\n👉 ¿Quieres configurar Gmail? (s/n): ", end="")
        if input().lower() == "s":
            self.gmail_setup()

        print("\n👉 ¿Quieres configurar Instagram? (s/n): ", end="")
        if input().lower() == "s":
            self.instagram_setup()

        print("\n" + "=" * 70)
        print("✅ CONFIGURACIÓN COMPLETADA")
        print("=" * 70)
        print("\nAhora puedes usar URA con todos los servicios configurados")
        print("=" * 70 + "\n")


if __name__ == "__main__":
    assistant = ConfigAssistant()
    assistant.full_setup()
