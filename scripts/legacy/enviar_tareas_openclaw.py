#!/usr/bin/env python3
"""
Envía 3 tareas concretas a OpenClaw vía core.openclaw_connector.

Antes de despachar:
  1. Verifica health_check de OpenClaw.
  2. Si OpenClaw no responde, aborta sin enviar nada.
  3. La contraseña del VPS se lee de la variable de entorno VPS_PASSWORD
     para no quedar en código ni en logs.

Uso:
    source .venv/bin/activate
    # VPS_PASSWORD debe estar en .env
    python3 scripts/enviar_tareas_openclaw.py
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

# Asegurar que el repo está en sys.path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.openclaw_connector import OpenClawConnector  # noqa: E402

VPS_IP = "146.59.229.191"
VPS_USER = "ubuntu"


def construir_tareas(vps_password: str) -> list[dict]:
    """Construye las 3 tareas. La contraseña se inyecta solo en memoria."""
    return [
        {
            "id": "tarea_1_vps_ssh",
            "titulo": "Acceso VPS OVHcloud y habilitación de SSH",
            "task": (
                f"Conéctate al VPS OVHcloud en IP {VPS_IP} con el usuario "
                f"'{VPS_USER}' y la contraseña proporcionada por la variable "
                "de entorno VPS_PASSWORD. Una vez dentro, verifica el estado "
                "del servicio SSH (`systemctl status ssh`), habilítalo si no "
                "está activo (`sudo systemctl enable --now ssh`), y reporta "
                "puertos abiertos relevantes (`ss -tlnp`). Devuelve un "
                "resumen con: estado SSH, puerto, último intento de login, "
                "y recomendaciones de hardening (deshabilitar PasswordAuth, "
                "usar SSH keys)."
            ),
            "context": {
                "vps_ip": VPS_IP,
                "vps_user": VPS_USER,
                "vps_password_env": "VPS_PASSWORD",
                "objetivo": "habilitar_ssh_y_hardening",
            },
        },
        {
            "id": "tarea_2_clawhub_skills",
            "titulo": "Recomendación de 10 skills seguras desde ClawHub",
            "task": (
                "Visita ClawHub (https://clawhub.openclaw.com o el índice "
                "oficial de skills de OpenClaw) y selecciona 10 skills que "
                "sean seguras y útiles para integrar en URA, una IA "
                "doméstica corriendo en un Mac mini M4. Para cada skill "
                "devuelve: nombre, autor, versión, breve descripción, "
                "permisos que requiere, riesgos potenciales, y justificación "
                "de por qué encaja con URA. Excluye skills que requieran "
                "ejecutar comandos privilegiados sin sandbox o que envíen "
                "datos a terceros sin cifrado."
            ),
            "context": {
                "destino": "URA",
                "limitaciones": ["Mac mini M4 16GB", "macOS 26.4.1"],
                "criterios_seguridad": ["sandbox", "cifrado", "open_source"],
            },
        },
        {
            "id": "tarea_3_asus_gx10",
            "titulo": "Informe de precios ASUS Ascent GX10 en España/Europa",
            "task": (
                "Busca el equipo ASUS Ascent GX10 en tiendas online de "
                "España y Europa (PCComponentes, Coolmod, Amazon ES, "
                "Mediamarkt, Alternate DE, LDLC FR, etc.) y genera un "
                "informe comparativo. Para cada tienda devuelve: URL, "
                "precio en EUR (sin IVA y con IVA si está disponible), "
                "stock, plazo de entrega, garantía. Al final del informe "
                "incluye: precio mínimo, máximo, mediana, tienda más "
                "barata con stock inmediato, y cualquier oferta vigente."
            ),
            "context": {
                "producto": "ASUS Ascent GX10",
                "regiones": ["ES", "EU"],
                "moneda": "EUR",
            },
        },
    ]


async def precheck_openclaw() -> bool:
    """health_check con timeout corto. True si OpenClaw responde."""
    print("[1/2] Health check de OpenClaw...", flush=True)
    oc = OpenClawConnector()
    try:
        healthy = await asyncio.wait_for(oc.health_check(), timeout=40)
    except TimeoutError:
        print("  ✗ Timeout en health_check (40s).", flush=True)
        return False
    except Exception as e:
        print(f"  ✗ Error en health_check: {e}", flush=True)
        return False
    if healthy:
        print("  ✓ OpenClaw responde.", flush=True)
    else:
        print("  ✗ OpenClaw no responde correctamente.", flush=True)
    return healthy


async def enviar_tareas(tareas: list[dict]) -> list[dict]:
    """Envía las tareas en serie y devuelve resultados."""
    oc = OpenClawConnector(timeout=300)
    resultados = []
    for i, t in enumerate(tareas, start=1):
        print(f"\n[2/2] Enviando tarea {i}/{len(tareas)}: {t['titulo']}", flush=True)
        res = await oc.execute(t["task"], context=t["context"])
        res["_id"] = t["id"]
        res["_titulo"] = t["titulo"]
        ok = res.get("success", False)
        elapsed = res.get("elapsed", 0)
        print(f"  {'✓' if ok else '✗'} success={ok} elapsed={elapsed:.1f}s", flush=True)
        if not ok:
            print(f"    error: {res.get('error', '')[:200]}", flush=True)
        resultados.append(res)
    return resultados


def main() -> int:
    vps_password = os.getenv("VPS_PASSWORD")
    if not vps_password:
        print(
            "ERROR: VPS_PASSWORD no definida.\n"
            "  export VPS_PASSWORD='...' && python3 scripts/enviar_tareas_openclaw.py",
            file=sys.stderr,
        )
        return 2

    # Precheck
    healthy = asyncio.run(precheck_openclaw())
    if not healthy:
        print(
            "\nABORTADO: OpenClaw no está activo. Configura provider keys "
            "(p.ej. ANTHROPIC_API_KEY / OPENAI_API_KEY) y vuelve a intentar.",
            file=sys.stderr,
        )
        return 3

    tareas = construir_tareas(vps_password)
    resultados = asyncio.run(enviar_tareas(tareas))

    # Guardar resultados
    out_dir = ROOT / "core" / "data" / "output"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / "openclaw_tareas_resultados.json"
    with open(out_file, "w", encoding="utf-8") as f:
        # No volcar la contraseña al disco
        safe = [{k: v for k, v in r.items() if k != "task"} for r in resultados]
        json.dump(safe, f, ensure_ascii=False, indent=2)
    print(f"\nResultados guardados en {out_file}")

    return 0 if all(r.get("success") for r in resultados) else 1


if __name__ == "__main__":
    sys.exit(main())
