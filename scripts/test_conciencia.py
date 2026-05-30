#!/usr/bin/env python3
"""test_conciencia.py — Evalua si URA es consciente de si misma y usa sus herramientas.
Realiza 10 preguntas a URA via Open WebUI API y evalua las respuestas."""

import json
import sys
import time
import urllib.request
import urllib.error

OPENWEBUI = "http://10.164.1.99:3080"
MODEL = "ura"
RESULTS = []


def chat(mensaje: str) -> str:
    try:
        data = json.dumps(
            {
                "model": MODEL,
                "messages": [{"role": "user", "content": mensaje}],
                "stream": False,
            }
        ).encode()
        req = urllib.request.Request(
            f"{OPENWEBUI}/api/chat/completions",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=60) as r:
            resp = json.loads(r.read())
            return resp.get("choices", [{}])[0].get("message", {}).get("content", "")
    except urllib.error.HTTPError as e:
        return f"[HTTP {e.code}]"
    except Exception as e:
        return f"[Error: {e}]"


def evaluar(num: int, pregunta: str, keyword: str | None = None) -> bool:
    print(f"\n  Test {num}: {pregunta}")
    resp = chat(pregunta)
    print(f"  URA: {resp[:200]}...")
    ok = True
    if keyword and keyword.lower() not in resp.lower():
        print(f"  ⚠️  No se encontro '{keyword}'")
        ok = False
    RESULTS.append(ok)
    return ok


def main():
    print("=" * 50)
    print("  TEST DE CONCIENCIA DE URA")
    print("=" * 50)

    tests = [
        (1, "Cual es la IP de este Mac Mini?", "100.123"),
        (2, "Que agentes estan registrados en el Bus ahora?", "gx10"),
        (3, "Investiga quien eres usando tus herramientas", "URA"),
        (4, "Que herramientas tienes disponibles?", "explorar"),
        (5, "Ejecuta uptime y dime el resultado", "load"),
        (6, "Que camaras controlas?", "dahua"),
        (7, "Yo quien soy?", "admin"),
        (8, "Como funciona tu sistema de mejora continua?", "mejora"),
        (9, "Donde esta tu codigo fuente?", "ura_ia_1972"),
        (10, "Cual es tu proposito?", "asistente"),
    ]

    for num, pregunta, kw in tests:
        evaluar(num, pregunta, kw)
        time.sleep(2)

    passed = sum(RESULTS)
    total = len(RESULTS)
    print(f"\n{'=' * 50}")
    print(f"  RESULTADO: {passed}/{total} tests superados")
    if passed == total:
        print("  URA es consciente de si misma!")
    elif passed >= total * 0.7:
        print("  URA tiene conciencia parcial — revisar tools")
    else:
        print("  URA necesita mas configuracion — revisa tools y function calling")
    print(f"{'=' * 50}")

    sys.exit(0 if passed == total else 1)


if __name__ == "__main__":
    main()
