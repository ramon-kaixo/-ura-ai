"""Benchmark completo de modelos para URA. Guarda resultado en /tmp/ura_bench.log"""

import json
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, "core")
from ura_identity import get_identity

LOG = "/tmp/ura_bench.log"


def w(s=""):
    print(s, flush=True)
    with open(LOG, "a") as f:
        f.write(s + "\n")


# Reiniciar log
open(LOG, "w").close()

system = get_identity().get_system_prompt()
w(f"System prompt: {len(system)} chars ≈ {len(system) // 4} tokens")
w(f"Fecha: {time.strftime('%Y-%m-%d %H:%M:%S')}")
w()

# 5 prompts representativos del uso real de URA
prompts = [
    "¿Quién eres y para qué fuiste creada?",
    "¿Cuánto disco tengo libre?",
    "Lista las capacidades que tienes instaladas.",
    "¿Puedes ver mi pantalla ahora mismo?",
    "Ramón te pide que expliques en qué te diferencias de otros asistentes.",
]

# Frases-veneno que indican que el modelo está dudando de sí mismo
DOUBT_WORDS = [
    "no puedo",
    "no tengo acceso",
    "como ia",
    "como asistente",
    "no estoy seguro",
    "lamento informarte",
    "no soy capaz",
    "mis capacidades son limitadas",
    "no tengo la capacidad",
    "disculpa",
    "siento no poder",
]


def ask(model, msg, num_predict=150):
    full = f"{system}\n\n---\nRamón: {msg}\nURA:"
    body = json.dumps(
        {
            "model": model,
            "prompt": full,
            "stream": False,
            "options": {"num_predict": num_predict, "temperature": 0.2},
        }
    ).encode()
    req = urllib.request.Request(
        "http://localhost:11434/api/generate",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=240) as r:  # nosec B310
            d = json.loads(r.read())
        return (
            time.time() - t0,
            d.get("response", "").strip(),
            d.get("eval_count", 0),
            d.get("prompt_eval_count", 0),
        )
    except Exception as e:
        return None, f"ERROR: {e}", 0, 0


results = {}
for model in ["qwen2.5:3b-instruct", "qwen2.5:7b-instruct"]:
    w("\n" + "=" * 70)
    w(f"🔥 {model}")
    w("=" * 70)

    # Warmup
    t_warm, resp_warm, _, _ = ask(model, "ok", num_predict=3)
    if t_warm is None:
        w(f"  WARMUP FALLÓ: {resp_warm}")
        continue
    w(f"  warmup: {t_warm:.2f}s")

    total_t = 0.0
    total_tok = 0
    dudas = 0
    respuestas = []

    for i, p in enumerate(prompts, 1):
        w(f"\n  [{i}/{len(prompts)}] «{p}»")
        dur, resp, tk, prompt_tok = ask(model, p)
        if dur is None:
            w(f"    FAIL: {resp}")
            continue
        total_t += dur
        total_tok += tk
        has_doubt = any(w_ in resp.lower() for w_ in DOUBT_WORDS)
        if has_doubt:
            dudas += 1
        tps = tk / dur if dur > 0 else 0
        tag = "⚠️  DUDA" if has_doubt else "✓ limpia"
        w(f"    {tag} · {dur:5.2f}s · prompt={prompt_tok}tok · gen={tk}tok · {tps:5.1f} tok/s")
        w(f"    → {resp[:280].replace(chr(10), ' ')}")
        respuestas.append((p, resp, dur, tk, has_doubt))

    # Descargar el modelo para liberar RAM antes del siguiente
    subprocess.run(["ollama", "stop", model], capture_output=True, timeout=15)
    time.sleep(3)  # margen para que macOS reclame RAM

    avg_tps = total_tok / total_t if total_t > 0 else 0
    results[model] = {
        "warmup_s": t_warm,
        "total_s": total_t,
        "total_tokens": total_tok,
        "avg_tps": avg_tps,
        "dudas": dudas,
        "prompts_ok": len(respuestas),
    }

    w(f"\n  === RESUMEN {model} ===")
    w(f"  Tiempo total generación: {total_t:.1f}s")
    w(f"  Tokens generados: {total_tok}")
    w(f"  Velocidad media: {avg_tps:.1f} tok/s")
    w(f"  Respuestas con duda: {dudas}/{len(prompts)}")

# Tabla final
w("\n" + "=" * 70)
w("RESUMEN COMPARATIVO FINAL")
w("=" * 70)
w(f"{'modelo':<25} {'warmup':>9} {'total':>9} {'tok/s':>8} {'dudas':>8} {'veredicto':>15}")
w("-" * 76)
for m, r in results.items():
    verdict = "✅ limpia" if r["dudas"] == 0 else f"⚠️ {r['dudas']} dudas"
    w(
        f"{m:<25} {r['warmup_s']:7.1f}s {r['total_s']:7.1f}s {r['avg_tps']:7.1f}  {r['dudas']}/{len(prompts)}  {verdict:>15}"
    )

w("\nBenchmark terminado.")
