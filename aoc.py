#!/usr/bin/env python3
"""
AOC — Arquitectura de Orquesta Coordinada
Director en Mac → Especialistas en GX10 (128GB cada uno)

Uso:
  python3 aoc.py "App de reservas para restaurante"
  python3 aoc.py --telegram
"""

import requests
import time
import os
import sys
from pathlib import Path

# Config — lee de .env si existe
OLLAMA = os.environ.get("OLLAMA_HOST", "http://gx10-ts:11434")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

# Intentar leer del archivo .env (para PM2 que no hereda env vars)
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    for line in env_file.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip().strip('"').strip("'")
            if key == "OLLAMA_HOST":
                OLLAMA = val
            if key == "TELEGRAM_TOKEN":
                TELEGRAM_TOKEN = val
            if key == "TELEGRAM_CHAT_ID":
                TELEGRAM_CHAT_ID = val
AOC_DIR = Path.home() / "AOC"

SPECIALISTS = {
    "planificador": {
        "model": "deepseek-r1:70b",
        "system": "Eres PLANIFICADOR de software. Crea planes detallados con: objetivo, requisitos, tecnologías, arquitectura, fases. Usa razonamiento profundo paso a paso.",
        "tokens": 800,
    },
    "arquitecto": {
        "model": "qwen2.5-coder:32b",
        "system": "Eres ARQUITECTO de software. Diseña: estructura de archivos, módulos, modelo de datos, interfaces, flujo de usuario. Usa nombres de archivo reales. Sé ultra-detallado.",
        "tokens": 800,
    },
    "constructor": {
        "model": "codestral:22b",
        "system": "Eres PROGRAMADOR experto. Escribe CÓDIGO COMPLETO y funcional. Archivos enteros con rutas. Código listo para compilar/ejecutar. Máxima calidad.",
        "tokens": 1500,
    },
    "revisor": {
        "model": "qwen3:32b-q8_0",
        "system": "Eres REVISOR de código. Encuentra errores, bugs, mejoras de seguridad. Sé crítico y específico. Indica líneas exactas a cambiar y por qué.",
        "tokens": 600,
    },
}


def ask(model, prompt, max_tokens=500):
    """Llama a Ollama GX10."""
    opts = {"num_predict": max_tokens}
    # deepseek-r1 necesita contexto reducido para caber en GPU
    if "deepseek" in model or "70b" in model:
        opts["num_ctx"] = 4096
    r = requests.post(
        f"{OLLAMA}/api/generate",
        json={"model": model, "prompt": prompt, "stream": False, "options": opts},
        timeout=600,
    )
    return r.json()["response"].strip(), r.json().get("total_duration", 0) // 1e6


def unload(model):
    """Descarga modelo para liberar RAM."""
    try:
        requests.post(
            f"{OLLAMA}/api/generate",
            json={
                "model": model,
                "prompt": ".",
                "stream": False,
                "keep_alive": 0,
                "options": {"num_predict": 1},
            },
            timeout=10,
        )
    except:
        pass
    time.sleep(3)


def run_aoc(task: str, use_telegram: bool = True):
    """Ejecuta las 4 fases AOC."""
    print(f"\n{'=' * 60}")
    print(f"🎯 AOC — {task[:60]}")
    print(f"{'=' * 60}")

    project = task.lower().replace(" ", "-")[:40]
    proj_dir = AOC_DIR / project
    proj_dir.mkdir(parents=True, exist_ok=True)

    if use_telegram:
        tg(f"🎯 *Nueva misión:* {task[:100]}\n📁 `{project}`")

    results = {}
    total_t = 0
    prev_model = None

    for i, (name, spec) in enumerate(SPECIALISTS.items(), 1):
        model = spec["model"]
        print(f"\n{'─' * 40}")
        print(f"🎭 FASE {i}/4: {name.upper()} ({model})")

        # Cambiar de modelo si es necesario
        if prev_model and model != prev_model:
            print(f"   🔄 Descargando {prev_model}...")
            unload(prev_model)

        # Construir contexto
        context = f"PROYECTO: {task}\n\n"
        for pn, pr in results.items():
            context += f"=== {pn.upper()} ===\n{pr[:2500]}\n\n"
        context += f"=== TU TAREA ({name.upper()}) ===\nHaz tu parte del trabajo."

        full_prompt = f"{spec['system']}\n\n{context}"

        response, t = ask(model, full_prompt, spec["tokens"])
        results[name] = response
        total_t += t
        prev_model = model

        # Guardar
        out_file = proj_dir / f"0{i}_{name}.md"
        out_file.write_text(f"# {name.upper()}\n\n{response}")
        print(f"   ✅ {t / 1000:.0f}s → {out_file.name}")

        if use_telegram:
            tg(f"✅ *{name.upper()}* → {t / 1000:.0f}s")

    # Resumen
    summary = f"🏁 *AOC COMPLETADO*\n⏱️ {total_t / 60000:.1f} min\n📁 `~/AOC/{project}/`"
    if use_telegram:
        tg(summary)

    print(f"\n{'=' * 60}")
    print(f"✅ {total_t / 60000:.1f} min → {proj_dir}")
    for f in sorted(proj_dir.glob("*.md")):
        print(f"   📄 {f.name}")
    print(f"{'=' * 60}")

    return results


def tg(text: str):
    """Envía mensaje por Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"},
            timeout=10,
        )
    except:
        pass


def telegram_bot():
    """Bot de Telegram para recibir órdenes."""
    if not TELEGRAM_TOKEN:
        print("❌ TELEGRAM_TOKEN no configurado en .env")
        return

    print("🤖 AOC Bot iniciado. Comandos:")
    print("   /aoc tu proyecto  → lanza el ciclo completo")
    print("   /status           → estado del sistema")

    last_update = 0
    while True:
        try:
            resp = requests.get(
                f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates",
                params={"offset": last_update + 1, "timeout": 30},
            ).json()

            for update in resp.get("result", []):
                last_update = update["update_id"]
                msg = update.get("message", {})
                text = msg.get("text", "")
                chat_id = str(msg.get("chat", {}).get("id", ""))

                global TELEGRAM_CHAT_ID
                TELEGRAM_CHAT_ID = chat_id

                if text.startswith("/aoc "):
                    task = text[5:]
                    tg("🎯 Recibido. Iniciando AOC...")
                    run_aoc(task)
                elif text == "/status":
                    tg("🟢 AOC online\nqwen3:32b + mistral-large\nGX10 conectado")
                elif text == "/start":
                    tg("🛡️ AOC listo. Mándame /aoc y tu proyecto.")
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    if "--telegram" in sys.argv:
        telegram_bot()
    elif len(sys.argv) > 1:
        run_aoc(" ".join(sys.argv[1:]))
    else:
        print("Uso: python3 aoc.py 'descripción del proyecto'")
        print("     python3 aoc.py --telegram")
