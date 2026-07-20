#!/usr/bin/env python3
"""CLI interactivo para el asistente conversacional."""

import httpx

BASE_URL = "http://localhost:8003"


def chat_loop() -> None:
    print("URA Assistant CLI  |  :q para salir  |  :m <modo> para cambiar modo")
    print("-" * 50)

    cid = ""
    mode = "conversacion"

    while True:
        try:
            msg = input("\n💬 Tu: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 ¡Hasta luego!")
            break

        if msg == ":q":
            print("👋 ¡Hasta luego!")
            break

        if msg.startswith(":m "):
            mode = msg[3:].strip()
            print(f"📐 Modo cambiado a: {mode}")
            continue

        if not msg:
            continue

        resp = httpx.post(
            f"{BASE_URL}/api/v1/chat",
            json={"message": msg, "conversation_id": cid, "mode": mode, "stream": False},
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"❌ Error: {resp.status_code} {resp.text[:200]}")
            continue

        data = resp.json()
        cid = data.get("conversation_id", cid)
        print(f"🤖 URA [{data.get('intent', '?')}]:")
        print(f"   {data['reply']}")


if __name__ == "__main__":
    chat_loop()
