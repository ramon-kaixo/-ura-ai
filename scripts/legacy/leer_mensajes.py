#!/usr/bin/env python3
"""
Modo UN1 — Panel unificado de mensajeria.
Lee Gmail, WhatsApp, Telegram e Instagram con un solo comando.

Uso:
    python scripts/leer_mensajes.py          # todos
    python scripts/leer_mensajes.py --gmail  # solo Gmail
    python scripts/leer_mensajes.py --insta  # solo Instagram
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("UN1")


def _print_header(source: str, emoji: str):
    print(f"\n{'=' * 60}")
    print(f"  {emoji}  {source}")
    print(f"{'=' * 60}")


def _leer_gmail():
    """Lee correos de Gmail."""
    try:
        from core.messaging_tools import read_gmail_sync

        _print_header("GMAIL", "📧")
        result = read_gmail_sync(max_emails=10)
        if result.get("success"):
            for email in result.get("messages", []):
                print(f"\n  📩 {email.get('subject', '(sin asunto)')}")
                print(f"     De: {email.get('from_name', '?')} <{email.get('from_email', '?')}>")
                snippet = email.get("snippet", "")[:150]
                if snippet:
                    print(f"     {snippet}")
            print(f"\n  ✅ {result.get('summary', '')}")
        else:
            print(
                f"  ⚠️  {result.get('error', result.get('summary', 'No se pudieron leer correos'))}"
            )
            print("  💡 Configurar: python core/config_assistant.py → Gmail")
    except ImportError:
        print("  ⚠️  google-auth no instalado. pip install google-auth google-auth-oauthlib")
    except Exception as e:
        print(f"  ❌ Error: {e}")


def _leer_instagram():
    """Lee DMs de Instagram (solo lectura)."""
    try:
        from core.messaging_tools import read_instagram_sync

        _print_header("INSTAGRAM", "📷")
        result = read_instagram_sync(max_threads=10)
        if result.get("ok"):
            for msg in result.get("messages", result.get("data", [])):
                if isinstance(msg, dict):
                    print(f"\n  💬 {msg.get('sender', '?')}: {msg.get('text', '')[:200]}")
                else:
                    print(f"  💬 {msg}")
        else:
            print(f"  ⚠️  {result.get('error', 'No se pudieron leer DMs')}")
            print("  💡 Configurar: python core/config_assistant.py → Instagram")
    except ImportError:
        print("  ⚠️  instagrapi no instalado. pip install instagrapi")
    except Exception as e:
        print(f"  ❌ Error: {e}")


def _leer_whatsapp():
    """Lee mensajes de WhatsApp Web (solo lectura)."""
    try:
        from core.messaging_tools import read_whatsapp_sync

        _print_header("WHATSAPP", "💬")
        result = read_whatsapp_sync(max_messages=10)
        if result.get("ok"):
            for msg in result.get("messages", result.get("data", [])):
                if isinstance(msg, dict):
                    print(f"\n  💬 {msg.get('sender', '?')}: {msg.get('text', '')[:200]}")
                else:
                    print(f"  💬 {msg}")
        else:
            print(f"  ⚠️  {result.get('error', 'No se pudieron leer mensajes')}")
    except ImportError:
        print("  ⚠️  playwright no instalado. pip install playwright && playwright install")
    except Exception as e:
        print(f"  ❌ Error: {e}")


def _leer_telegram():
    """Lee mensajes de Telegram (solo lectura)."""
    try:
        from core.messaging_tools import read_telegram_sync

        _print_header("TELEGRAM", "✈️")
        result = read_telegram_sync(max_messages=10)
        if result.get("ok"):
            for msg in result.get("messages", result.get("data", [])):
                if isinstance(msg, dict):
                    print(f"\n  💬 {msg.get('sender', '?')}: {msg.get('text', '')[:200]}")
                else:
                    print(f"  💬 {msg}")
        else:
            print(f"  ⚠️  {result.get('error', 'No se pudieron leer mensajes')}")
    except ImportError:
        print("  ⚠️  telethon no instalado. pip install telethon")
    except Exception as e:
        print(f"  ❌ Error: {e}")


def main():
    parser = argparse.ArgumentParser(description="URA Modo UN1 — Panel unificado de mensajeria")
    parser.add_argument("--gmail", action="store_true", help="Solo Gmail")
    parser.add_argument("--insta", action="store_true", help="Solo Instagram")
    parser.add_argument("--whatsapp", action="store_true", help="Solo WhatsApp")
    parser.add_argument("--telegram", action="store_true", help="Solo Telegram")
    args = parser.parse_args()

    all_selected = not any([args.gmail, args.insta, args.whatsapp, args.telegram])

    print(f"\n{'#' * 60}")
    print("#  URA — Modo UN1 (Mensajeria Unificada)")
    print(f"#  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'#' * 60}")

    if args.gmail or all_selected:
        _leer_gmail()
    if args.insta or all_selected:
        _leer_instagram()
    if args.whatsapp or all_selected:
        _leer_whatsapp()
    if args.telegram or all_selected:
        _leer_telegram()

    print(f"\n{'—' * 60}")
    print("✅ UN1 completado")
    print(f"{'—' * 60}\n")


if __name__ == "__main__":
    main()
